#!/usr/bin/env python3
"""Master Tracker v2 — import calls from Apollo into per-rep tabs of a Google Sheet.

Config-driven (no hardcoded org details). Reads ./config.json (or $MT_CONFIG).

v2 fix over v1: a call ID is only marked "ingested" once it has been written with a
KEEP disposition. Calls seen with a blank / non-KEEP disposition are NOT burned into
the skip list — they are re-checked every run inside a rolling window, so a call that
a rep tags AFTER the first pull (the common case) still gets picked up. v1 added every
seen ID to a skip set, which permanently lost late-tagged calls.

Per-rep tab schema (row 1 = header):
  A Date | B Prospect | C Company | D Title | E Recording | F Disposition |
  G Correct Disposition | H (manual) | I (manual)
"""
import json, os, re, sys, time
from datetime import datetime, timedelta, timezone
from urllib import request as urlreq, error as urlerr
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.environ.get('MT_CONFIG', os.path.join(HERE, 'config.json'))
STATE_PATH = os.path.join(HERE, 'state.json')
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

with open(CFG_PATH) as f: cfg = json.load(f)
KEEP = set(cfg.get('keep_dispositions', []))
KEEP_PREFIXES = tuple(cfg.get('keep_disposition_prefixes', []))
REPS = cfg['reps']
SHEET_ID = cfg['google']['sheet_id']
AUTOFILL_THROUGH = cfg.get('autofill_correct_disposition_through', '')
BACKFILL_DAYS = int(cfg.get('backfill_days', 30))
TR = cfg.get('trellus', {}) or {}

def _resolve(p):
    return p if os.path.isabs(p) else os.path.join(HERE, p)

with open(_resolve(cfg['google']['oauth_token_file'])) as f: tok = json.load(f)
with open(_resolve(cfg['google']['client_secret_file'])) as f:
    cs = json.load(f); cs = cs.get('installed', cs)
creds = Credentials(token=tok.get('access_token'), refresh_token=tok['refresh_token'],
    token_uri='https://oauth2.googleapis.com/token',
    client_id=cs['client_id'], client_secret=cs['client_secret'])
creds.refresh(Request())
svc = build('sheets', 'v4', credentials=creds)

def k(s): return str(s or '').strip().lower()
def pad(r, n): return r + [''] * (n - len(r))
def is_keep(d):
    return d in KEEP or any(d.startswith(p) for p in KEEP_PREFIXES)

def date_le(date_mdy, cutoff_iso):
    try:
        mo, d, y = date_mdy.split('/'); cy, cmo, cd = cutoff_iso.split('-')
        return (int(y), int(mo), int(d)) <= (int(cy), int(cmo), int(cd))
    except Exception:
        return False

# ── State: ingested KEEP call IDs only ──────────────────────────────────────
state = {'ingested_ids': []}
if os.path.exists(STATE_PATH):
    try: state = json.load(open(STATE_PATH))
    except Exception: pass
ingested = set(state.get('ingested_ids', []))

# ── Apollo POST with 429 backoff ────────────────────────────────────────────
def apost(path, body, retries=4):
    data = json.dumps(body).encode()
    for attempt in range(retries):
        req = urlreq.Request(f'https://api.apollo.io/api/v1{path}', data=data,
            headers={'X-Api-Key': cfg['apollo_api_key'], 'Content-Type': 'application/json',
                     'User-Agent': UA, 'Cache-Control': 'no-cache'})
        try:
            with urlreq.urlopen(req, timeout=30) as r:
                return {'ok': True, 'data': json.loads(r.read())}
        except urlerr.HTTPError as e:
            if e.code == 429:
                ra = e.headers.get('retry-after')
                wait = int(ra) if ra and ra.isdigit() else min(60 * (2 ** attempt), 900)
                print(f'  429; waiting {wait}s'); time.sleep(wait); continue
            return {'ok': False, 'code': e.code, 'body': e.read().decode()[:200]}
        except Exception as e:
            return {'ok': False, 'code': 0, 'body': str(e)[:200]}
    return {'ok': False, 'code': 429, 'body': 'retries exhausted'}

# ── Trellus public-link minting (optional) ──────────────────────────────────
SESSION_PAT = re.compile(r'(?:session_id|id)=([a-f0-9]+)')
def mint(session_id):
    if not (TR.get('api_key') and TR.get('team_id') and session_id):
        return f'https://app.trellus.ai/transcripts?id={session_id}' if session_id else ''
    try:
        r = requests.get('https://api.trellus.ai/get-session-access-token',
            headers={'Api_key': f'"{TR["api_key"]}"', 'Team_id': f'"{TR["team_id"]}"',
                     'Request': '"true"', 'Origin': 'https://app.trellus.ai',
                     'Session_id': f'"{session_id}"'}, timeout=10)
        if r.ok and r.json().get('session_access_token'):
            t = r.json()['session_access_token']
            return f'https://app.trellus.ai/view?access_token={t}&session_id={session_id}'
    except Exception:
        pass
    return f'https://app.trellus.ai/transcripts?id={session_id}'

# ── Pull window ─────────────────────────────────────────────────────────────
until = datetime.now(timezone.utc)
since = until - timedelta(days=BACKFILL_DAYS)
date_min, date_max = since.strftime('%Y-%m-%d'), until.strftime('%Y-%m-%d')
print(f'=== Master Tracker v2 — {until:%Y-%m-%d %H:%M UTC} | window {date_min}..{date_max} ===')

def fmt_date(s):
    if not s: return ''
    try: dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception: return ''
    return f'{dt.month}/{dt.day}/{dt.year}'

# ── 1. Pull per rep; collect KEEP rows in the window (re-check non-ingested) ──
per_rep = {}
mint_cache = {}
for rep_name, apollo_id in REPS.items():
    print(f'\n→ {rep_name}')
    rows, page = [], 1
    while page <= 30:
        res = apost('/phone_calls/search', {
            'user_ids': [apollo_id], 'date_range': {'min': date_min, 'max': date_max},
            'per_page': 100, 'page': page,
            'sort_by_field': 'phone_calls_end_time', 'sort_ascending': False})
        if not res['ok']:
            print(f'  error {res.get("code")}: {res.get("body")}'); break
        calls = res['data'].get('phone_calls', [])
        if not calls: break
        for c in calls:
            cid = c.get('id')
            if not cid or cid in ingested: continue
            dispo = (c.get('call_disposition') or c.get('phone_call_disposition')
                     or c.get('disposition') or '').strip()
            if not is_keep(dispo):
                continue   # v2: do NOT burn the id — re-check next run if it gets tagged
            notes = c.get('note_text') or c.get('notes') or c.get('note') or ''
            sm = SESSION_PAT.search(notes); session_id = sm.group(1) if sm else ''
            if session_id and session_id not in mint_cache:
                mint_cache[session_id] = mint(session_id)
            link = mint_cache.get(session_id, '')
            rows.append({
                'id': cid, 'date': fmt_date(c.get('end_time') or c.get('completed_at') or ''),
                'prospect': (c.get('contact_name') or (c.get('contact') or {}).get('name','') or '').strip(),
                'company':  (c.get('organization_name') or (c.get('contact') or {}).get('organization_name','') or '').strip(),
                'title':    ((c.get('contact') or {}).get('title') or '').strip(),
                'dispo': dispo, 'link': link})
        if len(calls) < 100: break
        page += 1; time.sleep(0.3)
    per_rep[rep_name] = rows
    print(f'  {len(rows)} KEEP rows queued')

# ── 2. Title enrichment from /contacts/search (fill blanks) ──────────────────
title_map = {}
if any(per_rep.values()):
    page = 1
    while page <= 20:
        res = apost('/contacts/search', {'contact_owner_ids': list(REPS.values()),
            'per_page': 100, 'page': page,
            'sort_by_field': 'contact_last_activity_date', 'sort_ascending': False})
        if not res['ok']: break
        cts = res['data'].get('contacts', [])
        if not cts: break
        for ct in cts:
            key = (k(ct.get('name')), k(ct.get('organization_name')))
            title_map.setdefault(key, ct.get('title') or '')
        if page >= min(res['data'].get('pagination', {}).get('total_pages', 1), 20): break
        page += 1; time.sleep(0.3)

# ── 3. Merge into rep tabs (append new rows; preserve existing G/H/I) ─────────
for rep_name, rows in per_rep.items():
    if rep_name not in {s['properties']['title'] for s in
                        svc.spreadsheets().get(spreadsheetId=SHEET_ID,
                            fields='sheets.properties').execute()['sheets']}:
        print(f'  WARN no tab: {rep_name}'); continue
    existing = svc.spreadsheets().values().get(spreadsheetId=SHEET_ID,
        range=f"'{rep_name}'!A2:I5000", valueRenderOption='FORMULA').execute().get('values', [])
    seen_keys = {(pad(e,9)[0], k(pad(e,9)[1])) for e in existing}
    appends = []
    appended_ids = []  # Track which IDs we actually append
    for r in rows:
        if not r['title']:
            r['title'] = title_map.get((k(r['prospect']), k(r['company'])), '')
        if not r['prospect'] or (r['date'], k(r['prospect'])) in seen_keys:
            continue
        rec = f'=HYPERLINK("{r["link"]}","View Recording")' if r['link'] else ''
        g = r['dispo'] if (r['date'] and AUTOFILL_THROUGH and date_le(r['date'], AUTOFILL_THROUGH)) else ''
        appends.append([r['date'], r['prospect'], r['company'], r['title'], rec, r['dispo'], g, '', ''])
        appended_ids.append(r['id'])  # Only mark as ingested if successfully appended
    if appends:
        start = len(existing) + 2
        svc.spreadsheets().values().update(spreadsheetId=SHEET_ID,
            range=f"'{rep_name}'!A{start}:I{start + len(appends) - 1}",
            valueInputOption='USER_ENTERED', body={'values': appends}).execute()
        # Only mark as ingested AFTER successful write
        for cid in appended_ids:
            ingested.add(cid)
    print(f'  {rep_name}: +{len(appends)} appended')
    time.sleep(0.3)

state['ingested_ids'] = list(ingested)
with open(STATE_PATH, 'w') as f: json.dump(state, f)
print(f'\n=== done — {len(ingested)} ingested ids tracked ===')
