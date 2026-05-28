#!/usr/bin/env python3
"""RC Pre-Brief sync — fills the Pre-Brief column (G) on the Meeting Board.

For each Meeting Board row that has a Call Recording (col H) but no Pre-Brief (col G):
  1. Pull the Trellus session_id from the col H recording HYPERLINK
  2. Transcribe the call (Deepgram -> Groq fallback)
  3. Ask Claude for the bullets that matter for this meeting (concerns / asks / context)
  4. Build an RC-branded Google Doc: key bullets (page 1) + full transcript (page 2),
     with each bullet anchored to the transcript line it came from
  5. Write a blue "View" HYPERLINK into col G

Idempotent: skips rows that already have a Pre-Brief link.
Env: PREBRIEF_ONLY=<substr> limits to matching prospect/company. PREBRIEF_LIMIT=<n> caps.
"""
import json, os, re, subprocess, sys, tempfile, time
from html import escape
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

with open(os.environ.get('SKILL_CONFIG', os.path.join(os.path.dirname(os.path.abspath(__file__)),'config.json'))) as f: cfg = json.load(f)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'_trellus.json')) as f: tc = json.load(f)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'google_token.json')) as f: t = json.load(f)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'client_secret.json')) as f: cs = json.load(f)['installed']
_env = dict(line.strip().split('=',1) for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'.env')) if '=' in line and not line.startswith('#'))
DG_KEY = _env.get('DEEPGRAM_API_KEY',''); GROQ_KEY = _env.get('GROQ_API_KEY','')
creds = Credentials(token=t['access_token'], refresh_token=t['refresh_token'],
    token_uri='https://oauth2.googleapis.com/token', client_id=cs['client_id'], client_secret=cs['client_secret'])
creds.refresh(Request())
svc = build('sheets','v4',credentials=creds)
drive = build('drive','v3',credentials=creds)
docs = build('docs','v1',credentials=creds)
def set_pageless(doc_id):
    try:
        docs.documents().batchUpdate(documentId=doc_id, body={'requests':[{'updateDocumentStyle':{'documentStyle':{'documentFormat':{'documentMode':'PAGELESS'}},'fields':'documentFormat.documentMode'}}]}).execute()
    except Exception: pass
SID = cfg['sheet_id']
BOARD = cfg.get('board_tab', 'Meeting Board')
_COL = cfg.get('columns', {})
CI_PROSPECT  = _COL.get('prospect', 2) - 1
CI_COMPANY   = _COL.get('company', 3) - 1
CI_PREBRIEF  = _COL.get('prebrief', 7) - 1
CI_RECORDING = _COL.get('recording', 8) - 1
CI_REP       = _COL.get('rep', 9) - 1
def _A1col(idx0):
    s=''; n=idx0+1
    while n: n,r=divmod(n-1,26); s=chr(65+r)+s
    return s
TH = {'Api_key': f'"{tc["api_key"]}"','Team_id': f'"{tc["team_id"]}"','Request':'"true"','Origin':'https://app.trellus.ai'}
CLAUDE_BIN = '/usr/bin/claude'

# RC palette
BRAND2='#fd5235'; BRAND1='#fe811e'; FG='#0d0d0d'; FGS='#2b2b2b'; MUTED='#6b6b6b'; LINE='#e6e3df'; BGW='#fff7ef'

def ts(s): m,x=divmod(int(s),60); return f'[{m:02d}:{x:02d}]'

def deepgram(url):
    try:
        r=requests.post('https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&punctuate=true',
            headers={'Authorization':f'Token {DG_KEY}','Content-Type':'application/json'},json={'url':url},timeout=120)
        if not r.ok: return None
        d=r.json(); return d.get('results',{}).get('channels',[{}])[0].get('alternatives',[{}])[0]
    except Exception: return None

def deepgram_segments(url):
    """Return [{start, text}] via Deepgram utterances. Primary transcription path (Groq has a
    low daily audio cap). Returns None on failure so the caller falls back to Groq."""
    if not DG_KEY: return None
    try:
        r=requests.post('https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&punctuate=true&utterances=true',
            headers={'Authorization':f'Token {DG_KEY}','Content-Type':'application/json'},json={'url':url},timeout=180)
        if not r.ok: return None
        utts=r.json().get('results',{}).get('utterances') or []
        segs=[{'start':u.get('start',0),'text':u.get('transcript','').strip()} for u in utts if u.get('transcript','').strip()]
        return segs or None
    except Exception: return None

def groq_segments(url):
    if not GROQ_KEY: return None
    try:
        tmp=tempfile.NamedTemporaryFile(suffix='.mp3',delete=False); tmp.close()
        with requests.get(url,stream=True,timeout=90) as resp:
            if not resp.ok: return None
            with open(tmp.name,'wb') as f:
                for ch in resp.iter_content(65536): f.write(ch)
        if os.path.getsize(tmp.name)<1000: os.unlink(tmp.name); return None
        res=subprocess.run(['curl','-s','-X','POST','https://api.groq.com/openai/v1/audio/transcriptions',
            '-H',f'Authorization: Bearer {GROQ_KEY}','-F',f'file=@{tmp.name}','-F','model=whisper-large-v3',
            '-F','response_format=verbose_json','-F','temperature=0'],capture_output=True,text=True,timeout=600)
        os.unlink(tmp.name)
        d=json.loads(res.stdout) if res.stdout.strip() else {}
        return d.get('segments')
    except Exception: return None

def fetch_segments(session_id, prospect, rep):
    """Return merged [(start, speaker, text)] across both channels. Channel 0 = prospect."""
    try:
        r=requests.get('https://api.trellus.ai/get-audio-links',headers={**TH,'Session_id':f'"{session_id}"'},timeout=15)
        urls=(r.json() if r.ok else {}).get('audio_links') or []
    except Exception: urls=[]
    merged=[]
    for idx,u in enumerate(urls):
        spk = prospect if idx==0 else rep
        # Deepgram primary (Groq has a low daily audio cap); Groq fallback.
        segs = deepgram_segments(u) or groq_segments(u)
        if not segs: continue
        for s in segs:
            merged.append((s['start'], spk, s['text'].strip()))
    merged.sort(key=lambda x:x[0])
    return merged

BULLET_PROMPT = '''You are prepping a sales rep for an upcoming meeting. Below is the transcript of the call that booked this meeting.

PROSPECT: {prospect}
COMPANY: {company}

TRANSCRIPT:
{transcript}

Extract the bullets that MATTER for the rep walking into this meeting — the prospect's concerns, questions, objections, asks, stated priorities, and any commitments made. Each bullet must be ONE concise line, grounded in something actually said. Lead with the most important. 5-8 bullets max.

For each bullet, also give the approximate timestamp (in seconds, integer) of the transcript moment it came from, so we can anchor it.

Output JSON ONLY (no fences, no prose):
{{"bullets": [{{"point": "<one concise line>", "t": <seconds int>}}, ...]}}'''

def call_claude(prompt, timeout=300):
    res = subprocess.run([CLAUDE_BIN,'-p',prompt], capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f'claude CLI failed (usage limit?): {res.stderr[-200:]}')
    return res.stdout.strip()

def extract_json(s):
    s=re.sub(r'```(?:json)?','',s).strip()
    a=s.find('{');
    if a<0: raise ValueError('no json')
    depth=0
    for i in range(a,len(s)):
        if s[i]=='{':depth+=1
        elif s[i]=='}':
            depth-=1
            if depth==0: return json.loads(s[a:i+1])
    raise ValueError('unbalanced json')

def build_doc(prospect, company, rep, recording_url, bullets, segments):
    anchor={}
    for i,b in enumerate(bullets,1):
        anchor.setdefault(int(b.get('t',0)),[]).append(i)
    P=[]
    P.append(f'<html><body style="font-family:Inter,Arial,sans-serif;font-size:11pt;line-height:1.5;color:{FG}">')
    P.append(f'<div style="background:{BGW};border-left:6px solid {BRAND2};padding:14pt 18pt;margin-bottom:14pt">')
    P.append(f'<div style="font-size:10pt;letter-spacing:0.22em;text-transform:uppercase;color:{BRAND2};font-weight:700">Pre-Brief</div>')
    P.append(f'<h1 style="font-size:22pt;margin:6pt 0 4pt 0">{escape(prospect)} — {escape(company)}</h1>')
    rec = f'<a href="{escape(recording_url)}" style="color:{BRAND2}">Call recording</a>' if recording_url else 'Call recording'
    P.append(f'<div style="color:{MUTED};font-size:10pt">Rep: {escape(rep)} · Source: {rec}</div></div>')
    P.append(f'<h2 style="font-size:13pt;text-transform:uppercase;letter-spacing:0.18em;margin:16pt 0 6pt 0">What matters going in</h2>')
    P.append(f'<div style="border-top:2px solid {FG};margin-bottom:10pt"></div>')
    for i,b in enumerate(bullets,1):
        P.append(f'<div style="padding:8pt 12pt;margin-bottom:6pt;background:#fff;border:1px solid {LINE};border-radius:6pt;border-left:4px solid {BRAND1}">'
                 f'<span style="color:{BRAND2};font-weight:700">{i:02d}.</span> <span style="font-weight:600">{escape(b.get("point",""))}</span></div>')
    if segments:
        P.append('<p style="page-break-before:always"></p>')
        P.append(f'<div style="background:{BGW};border-left:6px solid {BRAND2};padding:10pt 16pt;margin-bottom:12pt">'
                 f'<div style="font-size:10pt;letter-spacing:0.22em;text-transform:uppercase;color:{BRAND2};font-weight:700">Full transcript</div></div>')
        for start,spk,text in segments:
            st=int(start)
            if st in anchor:
                tags=', '.join(f'#{n}' for n in anchor[st])
                P.append(f'<div style="border-left:4px solid {BRAND2};background:#fff5ee;padding:8pt 12pt;margin:8pt 0;border-radius:0 6pt 6pt 0">'
                         f'<div style="color:{BRAND2};font-weight:700;font-size:9pt;text-transform:uppercase">▼ Point {tags}</div>'
                         f'<div style="margin-top:4pt"><span style="color:{MUTED};font-family:monospace;font-size:9pt">{ts(st)}</span> '
                         f'<b>{escape(spk)}:</b> <span style="color:{FGS}">{escape(text)}</span></div></div>')
            else:
                c = BRAND2 if spk==prospect else FG
                P.append(f'<p style="margin:3pt 0"><span style="color:{MUTED};font-family:monospace;font-size:9pt">{ts(st)}</span> '
                         f'<span style="color:{c};font-weight:700">{escape(spk)}:</span> <span style="color:{FGS}">{escape(text)}</span></p>')
    P.append('</body></html>')
    media=MediaIoBaseUpload(io.BytesIO('\n'.join(P).encode('utf-8')),mimetype='text/html',resumable=False)
    f=drive.files().create(body={'name':f'Pre-Brief — {prospect} ({company})','mimeType':'application/vnd.google-apps.document'},
                           media_body=media,fields='id,webViewLink').execute()
    set_pageless(f['id'])
    return f['webViewLink']

SID_PAT=re.compile(r'session_id=([a-f0-9]+)')
def pad(r,n): return r+['']*(n-len(r))

ONLY=os.environ.get('PREBRIEF_ONLY','').strip().lower()
LIMIT=int(os.environ.get('PREBRIEF_LIMIT','0') or 0)

_maxcol = _A1col(max(CI_PROSPECT,CI_COMPANY,CI_PREBRIEF,CI_RECORDING,CI_REP))
rows=svc.spreadsheets().values().get(spreadsheetId=SID,range=f"'{BOARD}'!A2:{_maxcol}300",
    valueRenderOption='FORMULA').execute().get('values',[])
todo=[]
for i,r in enumerate(rows,2):
    r=pad(r,max(CI_PROSPECT,CI_COMPANY,CI_PREBRIEF,CI_RECORDING,CI_REP)+1)
    prospect,company,prebrief,recording,rep=(str(r[CI_PROSPECT]).strip(),str(r[CI_COMPANY]).strip(),
        str(r[CI_PREBRIEF]).strip(),str(r[CI_RECORDING]).strip(),str(r[CI_REP]).strip())
    if not prospect or prebrief: continue           # already has a pre-brief
    m=SID_PAT.search(recording)
    if not m: continue                              # no recording to brief from
    if ONLY and ONLY not in prospect.lower() and ONLY not in company.lower(): continue
    todo.append({'row':i,'prospect':prospect,'company':company,'rep':rep,
                 'session_id':m.group(1),'recording':recording})
if LIMIT: todo=todo[:LIMIT]
print(f'Pre-Brief: {len(todo)} meetings need a brief')

made=skipped=failed=0
for it in todo:
    tag=f"Row {it['row']}: {it['prospect']} @ {it['company']}"
    try:
        segs=fetch_segments(it['session_id'], it['prospect'], it['rep'] or 'Rep')
        if not segs:
            print(f'  [skip] {tag}: no transcript'); skipped+=1; continue
        transcript='\n'.join(f"{ts(s)} {spk}: {txt}" for s,spk,txt in segs)[:14000]
        raw=call_claude(BULLET_PROMPT.format(prospect=it['prospect'],company=it['company'],transcript=transcript))
        bullets=extract_json(raw).get('bullets',[])
        if not bullets:
            print(f'  [skip] {tag}: no bullets'); skipped+=1; continue
        # recording public url from formula
        mu=re.search(r'"(https://app\.trellus\.ai/[^"]+)"', it['recording'])
        rec_url=mu.group(1) if mu else ''
        link=build_doc(it['prospect'],it['company'],it['rep'] or 'Rep',rec_url,bullets,segs)
        svc.spreadsheets().values().update(spreadsheetId=SID,range=f"'{BOARD}'!{_A1col(CI_PREBRIEF)}{it['row']}",
            valueInputOption='USER_ENTERED',body={'values':[[f'=HYPERLINK("{link}","View")']]}).execute()
        print(f'  [ok]   {tag}: {len(bullets)} bullets'); made+=1
    except Exception as e:
        print(f'  [fail] {tag}: {type(e).__name__} {str(e)[:140]}'); failed+=1
        if 'usage limit' in str(e).lower() or 'claude CLI failed' in str(e):
            print('  Team usage limit hit — stopping; cron will resume next run.'); break
print(f'\n=== done: {made} made, {skipped} skipped, {failed} failed ===')
