#!/usr/bin/env python3
"""RC deck-queue cron — generates decks back-to-back for Custom Decks rows where
Deck (col F) is blank. No artificial pacing — render_deck.py's exponential backoff
absorbs Drive 429s on the shared rclone OAuth project. A lockfile prevents the next
scheduled run from racing if the current one is still draining.

For each row needing a deck:
  1. Find the prospect's most-recent Activated Lead call in their rep tab
  2. Pull the Trellus session_id from col E recording HYPERLINK
  3. Transcribe the audio via Deepgram (if usable; some calls are too short)
  4. Pull company web-context (LinkedIn About / CBI / brand site if reachable)
  5. Synthesize deck tokens, write to os.path.join(os.path.dirname(os.path.abspath(__file__)),'rendered')/{slug}_tokens.json
  6. Render via os.path.join(os.path.dirname(os.path.abspath(__file__)),'render_deck.py')
  7. Write the Slides /preview link into Custom Decks col F as HYPERLINK("...", "View")
  8. Sleep PACE_SECONDS before next prospect

Re-runnable: skip rows where col F is already populated.

Run manually first, then add to crontab (e.g. every 4h).
"""
import json, re, time, requests, subprocess, os, sys
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

PACE_SECONDS = 0            # back-to-back; render_deck.py's Drive backoff handles 429s
MAX_PER_RUN  = 100          # drain the queue; lockfile keeps next cron run from racing
_HERE = os.path.dirname(os.path.abspath(__file__))
SLUG_DIR     = os.path.join(_HERE, 'rendered')
TEMPLATE_TOKENS = os.path.join(_HERE, 'template_tokens.json')
BUILD_DECK_PY = os.path.join(_HERE, 'build_deck.py')
RENDER_DECK_PY = os.path.join(_HERE, 'render_deck.py')

with open(os.environ.get('SKILL_CONFIG', os.path.join(os.path.dirname(os.path.abspath(__file__)),'config.json'))) as f: cfg = json.load(f)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'_trellus.json')) as f: tc = json.load(f)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'google_token.json')) as f: t = json.load(f)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'client_secret.json')) as f: cs = json.load(f)['installed']
_env = dict(line.strip().split('=',1) for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'.env')) if '=' in line and not line.startswith('#'))
DG_KEY   = _env.get('DEEPGRAM_API_KEY','')
GROQ_KEY = _env.get('GROQ_API_KEY','')

creds = Credentials(token=t['access_token'], refresh_token=t['refresh_token'],
    token_uri='https://oauth2.googleapis.com/token',
    client_id=cs['client_id'], client_secret=cs['client_secret'])
creds.refresh(Request())
svc = build('sheets', 'v4', credentials=creds)
sid = cfg['sheet_id']

TH = {'Api_key': f'"{tc["api_key"]}"', 'Team_id': f'"{tc["team_id"]}"',
      'Request': '"true"', 'Origin': 'https://app.trellus.ai'}

# ── Helpers ───────────────────────────────────────────────────────────────
def k(s): return str(s or '').strip().lower()
def pad(row, n): return row + [''] * (n - len(row))
def slugify(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')

REC_PAT = re.compile(r'session_id=([a-f0-9]+).*?access_token=([a-f0-9]+)|access_token=([a-f0-9]+).*?session_id=([a-f0-9]+)')

def parse_recording_formula(formula):
    """Return (session_id, access_token) from a HYPERLINK formula or empty strings."""
    if not formula: return '', ''
    m = re.search(r'access_token=([a-f0-9]+)', formula)
    tok = m.group(1) if m else ''
    m = re.search(r'session_id=([a-f0-9]+)', formula)
    sid_ = m.group(1) if m else ''
    return sid_, tok

def get_audio_links(session_id):
    r = requests.get('https://api.trellus.ai/get-audio-links',
        headers={**TH, 'Session_id': f'"{session_id}"'}, timeout=15)
    return r.json() if r.ok else {}

def deepgram(audio_url):
    """Transcribe a single audio URL via Deepgram nova-3. Returns transcript or ''."""
    try:
        r = requests.post(
            'https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&punctuate=true',
            headers={'Authorization': f'Token {DG_KEY}',
                     'Content-Type': 'application/json'},
            json={'url': audio_url}, timeout=120)
        if not r.ok: return ''
        d = r.json()
        return (d.get('results', {}).get('channels', [{}])[0]
                 .get('alternatives', [{}])[0].get('transcript', '')) or ''
    except Exception:
        return ''

def groq_transcribe(audio_url):
    """Fallback: download audio URL to /tmp and transcribe via Groq whisper-large-v3."""
    import subprocess, tempfile, os
    if not GROQ_KEY: return ''
    try:
        tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        tmp.close()
        # Stream audio to disk
        with requests.get(audio_url, stream=True, timeout=60) as resp:
            if not resp.ok: return ''
            with open(tmp.name, 'wb') as f:
                for chunk in resp.iter_content(65536): f.write(chunk)
        size = os.path.getsize(tmp.name)
        if size < 1000: os.unlink(tmp.name); return ''
        res = subprocess.run([
            'curl', '-s', '-X', 'POST',
            'https://api.groq.com/openai/v1/audio/transcriptions',
            '-H', f'Authorization: Bearer {GROQ_KEY}',
            '-F', f'file=@{tmp.name}',
            '-F', 'model=whisper-large-v3',
            '-F', 'response_format=json',
            '-F', 'temperature=0',
        ], capture_output=True, text=True, timeout=300)
        os.unlink(tmp.name)
        d = json.loads(res.stdout) if res.stdout.strip() else {}
        return d.get('text', '') or ''
    except Exception:
        return ''

def fetch_transcript(session_id):
    """Pull both party audio channels for a session, transcribe, return merged text."""
    al = get_audio_links(session_id)
    urls = al.get('audio_links') or []
    parts = []
    for u in urls:
        txt = deepgram(u)
        if not txt and GROQ_KEY:
            txt = groq_transcribe(u)
        if txt: parts.append(txt)
    return '\n---\n'.join(parts)

# Dispositions that qualify a rep-tab row as the source call for a deck.
DECK_SOURCE_DISPOS = {'Activated Lead', 'Meeting Scheduled', 'Nurture',
                      'Connect Incomplete - Send Propaganda'}

# Cache ALL rep tabs once per run (not per-deck) so we never hit the Sheets
# 60-reads/min throttle while draining the queue. Built lazily on first lookup.
_REP_TAB_CACHE = None
def _load_rep_tabs():
    global _REP_TAB_CACHE
    if _REP_TAB_CACHE is not None:
        return _REP_TAB_CACHE
    # Single batchGet across all rep tabs = 1 API call total.
    ranges = [f"'{rep}'!A2:I2000" for rep in cfg['reps']]
    resp = svc.spreadsheets().values().batchGet(
        spreadsheetId=sid, ranges=ranges,
        valueRenderOption='FORMULA').execute()
    cache = {}
    for rep, vr in zip(cfg['reps'].keys(), resp.get('valueRanges', [])):
        cache[rep] = vr.get('values', [])
    _REP_TAB_CACHE = cache
    return cache

def find_call_for_prospect(prospect, company, rep_filter=None):
    """Find the most-recent deck-worthy rep-tab row matching this prospect+company.
    Uses the in-memory rep-tab cache (one batchGet per run). If `rep_filter` is set
    (the Rep column on Custom Decks), only that rep's tab is searched.
    Return (rep, date_str, session_id, recording_formula) or None."""
    cache = _load_rep_tabs()
    reps_to_check = [rep_filter] if rep_filter and rep_filter in cache else cache.keys()
    for rep in reps_to_check:
        best = None
        for row in cache.get(rep, []):
            row = pad(row, 9)
            date_v, p, c, title, rec, dispo, _, _, _ = row
            if k(p) != k(prospect) or k(c) != k(company): continue
            if str(dispo).strip() not in DECK_SOURCE_DISPOS: continue
            sid_, tok = parse_recording_formula(str(rec))
            if not sid_: continue
            best = (rep, date_v, sid_, tok)
        if best: return best
    return None

# ── Main: walk queue ──────────────────────────────────────────────────────
print(f'Deck queue cron starting (no pacing, cap={MAX_PER_RUN}/run, Drive-backoff retries on 429)')
rows = svc.spreadsheets().values().get(spreadsheetId=sid,
    range="'Custom Decks'!A2:H500",
    valueRenderOption='FORMULA').execute().get('values', [])

todo = []
for i, row in enumerate(rows, 2):
    row = pad(row, 8)
    if not str(row[1]).strip(): continue   # Skip phantom rows with no prospect
    if str(row[5]).strip(): continue       # Deck column already populated
    todo.append({'row_num': i, 'prospect': str(row[1]).strip(),
                 'company': str(row[2]).strip(), 'website': str(row[3]).strip(),
                 'rep_authority': str(row[7]).strip()})

DECK_PRIORITY = os.environ.get('DECK_PRIORITY','').strip().lower()
if DECK_PRIORITY:
    todo.sort(key=lambda it: 0 if DECK_PRIORITY in it['prospect'].lower() else 1)
    if todo and DECK_PRIORITY in todo[0]['prospect'].lower():
        print(f'Priority match: "{todo[0]["prospect"]}" moved to front')
print(f'Queue: {len(todo)} rows need a deck')
if not todo:
    print('Nothing to build. Exiting.')
    sys.exit(0)

# Simple lockfile so two cron invocations don't race
LOCK = '/tmp/rc_deck_queue.lock'
if os.path.exists(LOCK):
    try:
        pid = int(open(LOCK).read().strip())
        os.kill(pid, 0)
        print(f'Another deck-queue run is in flight (pid {pid}); exiting.')
        sys.exit(0)
    except (ValueError, ProcessLookupError, PermissionError):
        os.unlink(LOCK)
with open(LOCK, 'w') as f: f.write(str(os.getpid()))

import atexit
atexit.register(lambda: os.path.exists(LOCK) and os.unlink(LOCK))

built = 0
for item in todo[:MAX_PER_RUN]:
  try:
    prospect = item['prospect']
    company  = item['company']
    print(f'\n=== Row {item["row_num"]}: {prospect} @ {company} ===')

    rep_authority = item.get('rep_authority','')
    call = find_call_for_prospect(prospect, company, rep_filter=rep_authority)
    if not call:
        # Fall back to any rep if the authority rep doesn't have an Activated Lead
        # row (shouldn't happen normally, but covers sheet drift).
        call = find_call_for_prospect(prospect, company)
    if not call:
        print('  No Activated Lead call found in rep tabs — skip')
        continue
    rep_name, date_v, session_id, access_token = call
    print(f'  Rep={rep_name} (authority={rep_authority}) | session={session_id[:12]}…')

    # Transcribe
    transcript = fetch_transcript(session_id)
    print(f'  Transcript: {len(transcript)} chars')

    # Scaffold tokens directly from the template (skip build_deck.py prep — its slug
    # function diverges from ours on companies with hyphens/special chars).
    slug = slugify(company)
    tokens_path = f'{SLUG_DIR}/{slug}_tokens.json'
    with open(TEMPLATE_TOKENS) as f: tokens = json.load(f)
    tokens['LOGO_PATH'] = ''   # text fallback unless a manual logo file exists

    # Minimum tokens for first-pass render. Reps can refine before send.
    first = (prospect.split()[0] if prospect else '')
    tokens.update({
        'COMPANY_NAME': company,
        'FIRST_NAME':   first,
        'SLIDE1_HOOK':  company,  # generic fallback; personalize overrides with prospect-specific hook
        'SHIFT_HEADLINE':  f'The way {company} acquires buyers is about to change.',
        'SHIFT_PUNCHLINE': 'Outbound is how you reach the ones who are not searching yet.',
        'SHIFT_BODY':      (f'{first}, the best-fit buyers for {company} mostly do not Google '
                            f'for what you sell.<br>They get pulled in by someone naming the '
                            f'problem for them.<br>That is the gap outbound fills.'),
        'SHIFT_STAT1_NUM':'1.2%','SHIFT_STAT1_HEAD':'Reply rate floor',
        'SHIFT_STAT1_BODY':'Below this, cold outbound stops being economical at scale.',
        'SHIFT_STAT2_NUM':'3x','SHIFT_STAT2_HEAD':'Pipeline lift',
        'SHIFT_STAT2_BODY':'Average pipeline expansion 90 days into a RevCentric engagement.',
        'SHIFT_STAT3_NUM':'30d','SHIFT_STAT3_HEAD':'Ramp',
        'SHIFT_STAT3_BODY':'Sequence, dialer, and disposition cadence live within a month.',
        'SHIFT_CLOSE':     f'RevCentric owns the sourcing, scripts, and dial rhythm so {company} can stay focused on closing.',
        'COMPETE_HEAD1':   'Most outbound vendors sell you software.',
        'COMPETE_HEAD2':   'RevCentric sells you the conversations.',
        'COMPETE_INTRO':   ('The category is full of tools that hand you a workbook and call it '
                            'done. We build the team, run the dials, and put booked meetings on '
                            'your calendar.'),
        'COMPETITOR_NAME': 'Tooling-first vendors',
        'COMPETITOR_TAGLINE': '"Build your own pipeline engine"',
        'COMPETITOR_LINE1': 'You hire the SDRs and own the ramp',
        'COMPETITOR_LINE2': 'You manage the lists, the cadence, the QA',
        'COMPETITOR_LINE3': 'Their dashboard shows activity, not outcomes',
        'COMPANY_TAGLINE': '"Done-for-you outbound, accountable to outcomes"',
        'COMPANY_LINE1':   'We bring the reps, the lists, and the dialer',
        'COMPANY_LINE2':   'Every call recorded, every conversation visible',
        'COMPANY_LINE3':   'We own the result, not just the activity',
        # NEVER paste raw transcript here — it reads as nonsense ("Hello? Yes. Who is this?").
        # The transcript informs reps' manual edits; the generated default stays clean + on-brand.
        'WHY_OUTBOUND_FITS': (
            f'Outbound fits {company} because the people who will eventually be your best '
            f'customers are not searching for you yet. The fastest way to reach them is to '
            f'name the problem before they do.'),
        'ICP_LABEL': company.lower(),
        'THEIR_TARGET_TITLE': 'decision maker',
        'SENDER_NAME': rep_name.split()[0],
        'SENDER_EMAIL': cfg['reps'].get(rep_name, {}).get('email','sales@example.com'),
    })
    # Clear LOGO_PATH if the file doesn't exist (text fallback in render_deck)
    lp = tokens.get('LOGO_PATH','')
    if lp and not os.path.exists(lp):
        tokens['LOGO_PATH'] = ''

    with open(tokens_path,'w') as f: json.dump(tokens, f, indent=2)
    print(f'  Tokens written: {tokens_path}')

    # ── Initial render: mints Slides ID + PDF (generic tokens). ──
    res = subprocess.run(['python3', RENDER_DECK_PY, '--tokens', tokens_path],
                          capture_output=True, text=True)
    if res.returncode != 0:
        print(f'  initial render failed: {res.stderr[-800:]}')
        continue
    init_out = res.stdout
    slides_id_match = None
    for line in init_out.splitlines():
        if line.startswith('SLIDES_LINK:'):
            m = re.search(r'/d/([a-zA-Z0-9_-]+)/', line)
            if m: slides_id_match = m.group(1)
            break

    # Personalize step — re-enabled 2026-05-21 per Nelson's request.
    # Uses `claude -p` which burns Nelson's claude.ai Team chat quota.
    website = item.get('website','') or ''
    res2 = subprocess.run([
        'python3', os.path.join(_HERE,'personalize.py'),
        '--tokens', tokens_path,
        '--slides-id', slides_id_match or '',
        '--website', website,
        '--transcript', transcript,
    ], capture_output=True, text=True, timeout=900)
    if res2.returncode == 0 and res2.stdout.strip():
        print(f'  personalized OK')
        # Re-render with updated tokens so we get PUB_LINK + pdf
        res3 = subprocess.run(['python3', RENDER_DECK_PY, '--tokens', tokens_path,
                               '--slides-id', slides_id_match or ''],
                              capture_output=True, text=True)
        if res3.returncode == 0:
            out = res3.stdout
        else:
            print(f'  re-render after personalize failed: {res3.stderr[-400:]}')
            out = init_out
    else:
        print(f'  personalize failed/empty, using initial render. stderr: {res2.stderr[-300:]}')
        out = init_out
    deck_url = ''
    pdf_path = ''
    for line in out.splitlines():
        if line.startswith('PUB_LINK:'):
            deck_url = line.split('PUB_LINK:',1)[1].strip()
        elif line.startswith('pdf: '):
            pdf_path = line.split('pdf: ',1)[1].strip()
    print(f'  deck: {deck_url}')

    # ── Self-check before writing to sheet ────────────────────────────────
    checks = []
    # 1. PDF exists on disk
    if pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 50_000:
        checks.append('pdf OK')
    else:
        checks.append('pdf MISSING')
    # 2. /preview URL responds publicly (HEAD, allow redirects)
    try:
        rr = requests.head(deck_url, timeout=10, allow_redirects=True)
        if 200 <= rr.status_code < 400:
            checks.append(f'preview OK ({rr.status_code})')
        else:
            checks.append(f'preview FAIL ({rr.status_code})')
    except Exception as e:
        checks.append(f'preview ERR ({type(e).__name__})')
    # 3. Token budgets respected — re-check the stored tokens against limits
    with open(tokens_path) as f: final_tokens = json.load(f)
    BUDGETS = {
        'SHIFT_HEADLINE':80,'SHIFT_PUNCHLINE':70,'SHIFT_BODY':260,
        'SHIFT_CLOSE':180,'COMPETE_INTRO':240,'WHY_OUTBOUND_FITS':420,
    }
    overflows = [k for k,b in BUDGETS.items()
                 if len(re.sub(r'<[^>]+>', '', final_tokens.get(k,''))) > b]
    if overflows:
        checks.append(f'tokens OVERFLOW: {overflows}')
    else:
        checks.append('tokens OK')
    # 4. Transcript-artifact / nonsense detection — catches raw call snippets that
    # would read as gibberish on a slide.
    nonsense_tokens = []
    for k_ in ('SHIFT_HEADLINE','SHIFT_PUNCHLINE','SHIFT_BODY','SHIFT_CLOSE',
              'COMPETE_INTRO','WHY_OUTBOUND_FITS'):
        v = (final_tokens.get(k_) or '').strip()
        if not v: continue
        artifact = (v.count('?') >= 2 or
                    v.lower().lstrip().startswith(('hello','yes ','yes.','who is',
                                                    'hi.','hey ','um ','uh ','okay,')))
        if artifact: nonsense_tokens.append(k_)
    if nonsense_tokens:
        checks.append(f'tokens NONSENSE: {nonsense_tokens}')
    # 5. Generic-template guard — if personalize failed/fallback, block the write
    _body = re.sub(r'<[^>]+>', '', final_tokens.get('SHIFT_BODY', '')).lower()
    if 'do not google' in _body or 'mostly do not google' in _body:
        checks.append('tokens GENERIC')
    else:
        checks.append('content OK')
    print(f'  self-check: {" | ".join(checks)}')

    # Only write to sheet if all critical checks passed
    critical_fail = any('MISSING' in c or 'FAIL' in c or 'OVERFLOW' in c or 'NONSENSE' in c or 'GENERIC' in c for c in checks)
    if critical_fail or not deck_url:
        print(f'  SKIP write (self-check failed); deck file still saved at {pdf_path}')
        continue

    # Write to Custom Decks col F
    formula = f'=HYPERLINK("{deck_url}","View")'
    svc.spreadsheets().values().update(spreadsheetId=sid,
        range=f"'Custom Decks'!F{item['row_num']}",
        valueInputOption='USER_ENTERED', body={'values':[[formula]]}).execute()
    print(f'  Written to row {item["row_num"]} col F')
    built += 1
  except Exception as e:
    print(f'  CRASH on {item.get("prospect","?")}: {type(e).__name__}: {str(e)[:200]}')
    continue

  if PACE_SECONDS and built < MAX_PER_RUN and built < len(todo):
      print(f'  Sleeping {PACE_SECONDS}s before next…')
      time.sleep(PACE_SECONDS)

print(f'\nDone. Built {built} deck(s). {len(todo)-built} still in queue.')
