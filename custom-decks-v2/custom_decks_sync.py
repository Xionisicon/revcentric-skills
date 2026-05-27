#!/usr/bin/env python3
"""RC Custom Decks sync — Activated Lead rows from rep tabs → 8-col Custom Decks.

Schema A-H: Activated Date | Prospect | Company | Website | Email | Deck | Status | Rep

Rules (human-edits-supercede):
- Match existing rows by (prospect_lower, company_lower).
- For matched rows: only fill A-E (Date, Prospect, Company, Website, Email) when blank.
  Never touch F (Deck), G (Status checkbox), H (Rep manual override).
- For new rows: blank Deck and Status. Status checkbox stamped via batchUpdate.
- Apollo enriches Website + Email when blank. Website is HEAD-checked; bogus sites blanked.
- Dedup by (prospect, company), keep most-recent call date.
- Sort by Date ASC (earliest at top).
"""
import os
import json, re, requests, time
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

with open(os.environ.get('SKILL_CONFIG', os.path.join(os.path.dirname(os.path.abspath(__file__)),'config.json'))) as f: cfg = json.load(f)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'google_token.json')) as f: t = json.load(f)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'client_secret.json')) as f: cs = json.load(f)['installed']
creds = Credentials(token=t['access_token'], refresh_token=t['refresh_token'],
    token_uri='https://oauth2.googleapis.com/token',
    client_id=cs['client_id'], client_secret=cs['client_secret'])
creds.refresh(Request())
svc = build('sheets', 'v4', credentials=creds)
sid = cfg['sheet_id']

AH = {'X-Api-Key': cfg['api_key'], 'Content-Type': 'application/json'}

def k(s): return str(s or '').strip().lower()
def pad(row, n): return row + [''] * (n - len(row))
def serial_to_date(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        from datetime import timedelta
        dt = datetime(1899, 12, 30) + timedelta(days=float(v))
        return f'{dt.month}/{dt.day}/{dt.year}'
    return str(v).strip()
def date_key(d):
    """Parse 'M/D/YYYY' OR a Sheets serial int/float into a datetime."""
    if isinstance(d, (int, float)) and not isinstance(d, bool):
        from datetime import timedelta
        return datetime(1899, 12, 30) + timedelta(days=float(d))
    try:
        m, dd, y = str(d).split('/')
        return datetime(int(y), int(m), int(dd))
    except Exception:
        return datetime.max

def site_ok(url):
    """HEAD-check a URL; return True only on 2xx/3xx."""
    if not url: return False
    try:
        r = requests.head(url, timeout=6, allow_redirects=True,
                          headers={'User-Agent':'Mozilla/5.0'})
        return 200 <= r.status_code < 400
    except Exception:
        return False

# Dispositions that warrant a deck. The GATE IS COL F (the actual disposition) —
# these copy to Custom Decks regardless of QA / Correct-Disposition (col G) review.
CUSTOM_DECK_DISPOS = {
    'Activated Lead', 'Meeting Scheduled', 'Nurture',
    'Connect Incomplete - Send Propaganda',
}

# ── 1. Read all rep tabs (one batchGet), collect rows whose disposition (col F) qualifies ─
reps = list(cfg['reps'].keys())
_ranges = [f"'{rep}'!A2:I2000" for rep in reps]
_resp = svc.spreadsheets().values().batchGet(spreadsheetId=sid, ranges=_ranges,
    valueRenderOption='UNFORMATTED_VALUE').execute()
calls = []
for rep, vr in zip(reps, _resp.get('valueRanges', [])):
    for row in vr.get('values', []):
        row = pad(row, 9)
        date, prospect, company, title, recording, dispo_f, dispo_g, _, _ = row
        dispo = str(dispo_f).strip()
        if dispo not in CUSTOM_DECK_DISPOS: continue
        prospect = str(prospect).strip()
        company  = str(company).strip()
        if not prospect or not company: continue
        calls.append({'date': serial_to_date(date), 'prospect': prospect,
                      'company': company, 'rep': rep, 'dispo': dispo})

print(f'Found {len(calls)} qualifying rows across rep tabs (disposition col F ∈ '
      f'{sorted(CUSTOM_DECK_DISPOS)})')

# ── 2. Dedup by (prospect, company); keep most-recent call ────────────────
# TODO: multi-deck-per-lead (Activated Lead AND Meeting Scheduled = 2 decks) requires
# adding a Disposition column to the Custom Decks schema. Until then, one deck per lead,
# keyed to the most-recent qualifying call. The dispo value is preserved on the row for
# downstream use.
dedup = {}
for c in calls:
    key = (k(c['prospect']), k(c['company']))
    if key not in dedup or date_key(c['date']) > date_key(dedup[key]['date']):
        dedup[key] = c
unique = list(dedup.values())
print(f'Deduped to {len(unique)} unique prospects')

# ── 3. Enrich with Apollo (website + email) ───────────────────────────────
print('Enriching with Apollo data…')
rep_ids = [r['apollo_id'] for r in cfg['reps'].values()]
enrichment = {}  # (name_lower, company_lower) → {website, email}
page = 1
while True:
    r = requests.post('https://api.apollo.io/v1/contacts/search',
        json={'contact_owner_ids': rep_ids, 'per_page': 100, 'page': page,
              'sort_by_field': 'contact_last_activity_date', 'sort_ascending': False},
        headers=AH, timeout=30)
    if not r.ok: break
    d = r.json()
    contacts = d.get('contacts', [])
    if not contacts: break
    for ct in contacts:
        key = (k(ct.get('name')), k(ct.get('organization_name')))
        if key in enrichment: continue
        org = ct.get('organization') or {}
        web = org.get('website_url') or org.get('primary_domain') or ''
        if web and not web.startswith('http'):
            web = 'https://' + web.lstrip('/')
        enrichment[key] = {'website': web, 'email': ct.get('email') or ''}
    tp = d.get('pagination', {}).get('total_pages', 1)
    if page >= min(tp, 20): break
    page += 1
    time.sleep(0.2)
print(f'  Indexed {len(enrichment)} contacts')

# ── 4. Read existing Custom Decks (8 cols: A-H) ────────────────────────
# Schema: A=Date B=Prospect C=Company D=Website E=Email F=Deck G=Status H=Rep
existing = svc.spreadsheets().values().get(spreadsheetId=sid,
    range="'Custom Decks'!A2:H500",
    valueRenderOption='FORMULA').execute().get('values', [])
manual_map = {}  # (prospect_lower, company_lower) → existing row
for ex in existing:
    ex = pad(ex, 8)
    key = (k(ex[1]), k(ex[2]))
    if key[0] or key[1]:
        manual_map[key] = ex

# ── 5. Existing checkbox states for col G (Status) ────────────────────────
existing_status = svc.spreadsheets().values().get(spreadsheetId=sid,
    range="'Custom Decks'!A2:G500",
    valueRenderOption='UNFORMATTED_VALUE').execute().get('values', [])
prev_status = {}
for ex in existing_status:
    ex = pad(ex, 7)
    key = (k(ex[1]), k(ex[2]))
    prev_status[key] = bool(ex[6]) if ex[6] not in (None, '') else False

# ── 6. Build merged rows ──────────────────────────────────────────────────
merged_rows = []
new_keys = set()
verified_sites = {}  # cache HEAD checks
for u in unique:
    key = (k(u['prospect']), k(u['company']))
    new_keys.add(key)
    enrich = enrichment.get(key, {})
    apollo_web = enrich.get('website', '')
    apollo_email = enrich.get('email', '')

    if key in manual_map:
        ex = manual_map[key]
        # Preserve user-set fields where present; only fill blanks.
        # Rep (col H) ALWAYS from rep-tab source.
        date    = serial_to_date(ex[0]) if ex[0] else u['date']
        prospect = ex[1] or u['prospect']
        company  = ex[2] or u['company']
        website  = ex[3]
        if not website.strip() and apollo_web:
            if apollo_web not in verified_sites:
                verified_sites[apollo_web] = site_ok(apollo_web)
            website = apollo_web if verified_sites[apollo_web] else ''
        email    = ex[4] or apollo_email
        deck     = ex[5]   # NEVER overwrite
        rep      = u['rep']
        merged_rows.append([date, prospect, company, website, email, deck, '', rep])
    else:
        web = ''
        if apollo_web:
            if apollo_web not in verified_sites:
                verified_sites[apollo_web] = site_ok(apollo_web)
            if verified_sites[apollo_web]:
                web = apollo_web
        merged_rows.append([u['date'], u['prospect'], u['company'],
                            web, apollo_email, '', '', u['rep']])

# Sort ASC by date
merged_rows.sort(key=lambda r: date_key(r[0]))

# ── 7. Write A-F + H (skip G — handled via batchUpdate for checkboxes) ────
meta = svc.spreadsheets().get(spreadsheetId=sid, fields='sheets.properties').execute()
ad_sid = next(s['properties']['sheetId'] for s in meta['sheets']
              if s['properties']['title'] == 'Custom Decks')

n = len(merged_rows)
# Write A-F (Date/Prospect/Company/Website/Email/Deck) and H (Rep). Skip G (Status checkbox).
svc.spreadsheets().values().update(spreadsheetId=sid,
    range=f"'Custom Decks'!A2:F{n+1}",
    valueInputOption='USER_ENTERED',
    body={'values': [r[:6] for r in merged_rows]}).execute()
svc.spreadsheets().values().update(spreadsheetId=sid,
    range=f"'Custom Decks'!H2:H{n+1}",
    valueInputOption='USER_ENTERED',
    body={'values': [[r[7]] for r in merged_rows]}).execute()

# Clear any rows past n
prev_n = len(existing)
if prev_n > n:
    svc.spreadsheets().values().clear(spreadsheetId=sid,
        range=f"'Custom Decks'!A{n+2}:H{prev_n+1}").execute()

# Stamp Status checkboxes (col G = index 6) for all rows, restoring prior state.
EMPTY_CHECKBOX_RANGE_END = 100
reqs = []
for i, r_ in enumerate(merged_rows):
    key = (k(r_[1]), k(r_[2]))
    state = prev_status.get(key, False)
    reqs.append({
        'updateCells': {
            'range': {'sheetId': ad_sid, 'startRowIndex': 1+i, 'endRowIndex': 2+i,
                      'startColumnIndex': 6, 'endColumnIndex': 7},
            'rows': [{'values': [{'userEnteredValue': {'boolValue': bool(state)},
                                   'dataValidation': {'condition': {'type': 'BOOLEAN'}}}]}],
            'fields': 'userEnteredValue,dataValidation'
        }
    })
for i in range(len(merged_rows), EMPTY_CHECKBOX_RANGE_END - 1):
    reqs.append({
        'updateCells': {
            'range': {'sheetId': ad_sid, 'startRowIndex': 1+i, 'endRowIndex': 2+i,
                      'startColumnIndex': 6, 'endColumnIndex': 7},
            'rows': [{'values': [{'userEnteredValue': {'boolValue': False},
                                   'dataValidation': {'condition': {'type': 'BOOLEAN'}}}]}],
            'fields': 'userEnteredValue,dataValidation'
        }
    })
for i in range(0, len(reqs), 200):
    svc.spreadsheets().batchUpdate(spreadsheetId=sid,
        body={'requests': reqs[i:i+200]}).execute()

matched = len(manual_map.keys() & new_keys)
bogus_skipped = sum(1 for ok in verified_sites.values() if not ok)
print(f'Custom Decks: {n} rows. {matched} matched (manual edits preserved), '
      f'{n - matched} new. {bogus_skipped} bogus websites skipped. '
      f'Status checkboxes preserved.')
