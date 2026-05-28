#!/usr/bin/env python3
"""Rebuild an Overall Statistics tab from rep tabs + a meetings board.

Reads from the same config.json as apollo_pull.py; add an "overall_stats" block
for optional overrides (tab names, column positions, disposition labels).

Layout preserved (21 rows, A:J):
  Row 1   — timestamp (merged A1:J1)
  Row 2   — section headers: Statistics | ICP Report (D:G) | 10-Week Overview (I:J)
  Row 3   — column headers
  Rows 4-13 — OUTCOMES metrics (A:B) + ICP personas (D:G) + 10-Week (I:J)
  Row 14  — section headers: Rep Breakdown (D:G) | Leaderboard (I:J)
  Row 15  — sub-headers
  Rows 16-20 — disposition breakdown (A:B) + per-rep stats (D:J)
  Row 21  — footer

ICP Report uses wildcard COUNTIFS against the Title column of each rep tab,
so freeform titles ("Co-Founder & CEO", "Head of Growth & Marketing") match
the right bucket without manual cleanup.
"""
import json
import os
from datetime import datetime, timezone
from itertools import zip_longest
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

cfg_path = os.environ.get('SKILL_CONFIG', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json'))
with open(cfg_path) as f:
    cfg = json.load(f)

g = cfg['google']
with open(g['oauth_token_file']) as f: t = json.load(f)
with open(g['client_secret_file']) as f: cs = json.load(f)['installed']
creds = Credentials(token=t['access_token'], refresh_token=t['refresh_token'],
    token_uri='https://oauth2.googleapis.com/token',
    client_id=cs['client_id'], client_secret=cs['client_secret'])
creds.refresh(Request())
svc = build('sheets', 'v4', credentials=creds)
sid = g['sheet_id']

oc = cfg.get('overall_stats', {})
STATS_TAB   = oc.get('tab', 'Overall Statistics')
BOARD_TAB   = oc.get('board_tab', 'Meeting Board')
BOARD_DATE  = oc.get('board_col_date', 1)          # 1-indexed, col A default
BOARD_QUAL  = oc.get('board_col_qualification', 4)  # col D default
BOARD_SHOW  = oc.get('board_col_show_status', 5)    # col E default
BOARD_SCORE = oc.get('board_col_score', 6)          # col F default
BOARD_REP   = oc.get('board_col_rep', 9)            # col I default
REP_TITLE   = oc.get('rep_col_title', 4)            # col D in rep tabs
REP_DISPO   = oc.get('rep_col_dispo', 6)            # col F in rep tabs
QUAL_LABEL  = oc.get('qualified_label', 'Qualified')
SHOW_LABEL  = oc.get('show_label', 'Showed')
ACT_DISPO   = oc.get('activated_dispo', 'Activated Lead')
NUR_DISPO   = oc.get('nurture_dispo', 'Nurture')
BOOKED      = oc.get('booked_dispositions',
                     ['Meeting Scheduled', 'Meeting Confirmed', 'Rescheduled', 'Needs Rescheduled'])

def _col(n):
    """1-indexed column number → A1 letter."""
    s, n = '', n
    while n: n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s

REPS       = list(cfg['reps'].keys())
REP_DCOL   = _col(REP_TITLE)   # e.g. 'D'
REP_FCOL   = _col(REP_DISPO)   # e.g. 'F'
BOARD_ACOL = _col(BOARD_DATE)
BOARD_DCOL = _col(BOARD_QUAL)
BOARD_ECOL = _col(BOARD_SHOW)
BOARD_FCOL = _col(BOARD_SCORE)
BOARD_ICOL = _col(BOARD_REP)

def sum_dispo(dispo):
    parts = [f"COUNTIF('{r}'!{REP_FCOL}:{REP_FCOL},\"{dispo}\")" for r in REPS]
    return "=" + "+".join(parts)

def sum_booked():
    parts = [f"COUNTIF('{r}'!{REP_FCOL}:{REP_FCOL},\"{d}\")" for r in REPS for d in BOOKED]
    return "=" + "+".join(parts)

def sum_all():
    parts = [f"COUNTA('{r}'!{REP_FCOL}2:{REP_FCOL})" for r in REPS]
    return "=" + "+".join(parts)

def rep_booked(rep):
    parts = [f"COUNTIF('{rep}'!{REP_FCOL}:{REP_FCOL},\"{d}\")" for d in BOOKED]
    return "=" + "+".join(parts)


def rep_dispo(rep, dispo):
    return f"=COUNTIF('{rep}'!{REP_FCOL}:{REP_FCOL},\"{dispo}\")"

def icp_meetings(patterns):
    parts = [f"COUNTIFS('{r}'!{REP_DCOL}:{REP_DCOL},\"{p}\",'{r}'!{REP_FCOL}:{REP_FCOL},\"{d}\")"
             for p in patterns for r in REPS for d in BOOKED]
    return "=" + "+".join(parts)

def icp_dispo(patterns, dispo):
    parts = [f"COUNTIFS('{r}'!{REP_DCOL}:{REP_DCOL},\"{p}\",'{r}'!{REP_FCOL}:{REP_FCOL},\"{dispo}\")"
             for p in patterns for r in REPS]
    return "=" + "+".join(parts)

def week_label(n):
    base = f"TODAY()-WEEKDAY(TODAY()-1,2){f'-7*{n}' if n else ''}"
    return f'=TEXT({base},"M/D")&" - "&TEXT({base}+6,"M/D")'

def week_meetings(n):
    base = f"TODAY()-WEEKDAY(TODAY()-1,2){f'-7*{n}' if n else ''}"
    bcol = f"'{BOARD_TAB}'!{BOARD_ACOL}:{BOARD_ACOL}"
    return f"=SUMPRODUCT(({bcol}>={base})*({bcol}<={base}+6))"

# ICP personas — override via config key "icp_personas" if needed
ICP = oc.get('icp_personas', [
    ["CEO",            ["*ceo*"]],
    ["Founder",        ["*founder*"]],
    ["President",      ["*president*"]],
    ["Owner",          ["*owner*"]],
    ["CRO",            ["*cro*", "*chief revenue*"]],
    ["VP of Sales",    ["*vp*sales*", "*vice president*sales*"]],
    ["Head of Sales",  ["*head of sales*"]],
    ["VP of Marketing",["*vp*market*", "*cmo*", "*chief market*"]],
    ["COO",            ["*coo*", "*chief operat*"]],
    ["Head of Growth", ["*head of growth*", "*vp*growth*"]],
])

# A-col metrics (rows 4-13), parallel to ICP + 10-Week
bd, be, bf = f"'{BOARD_TAB}'", BOARD_DCOL, BOARD_ECOL
A_COL_4_13 = [
    ('Qualified Meetings',    f'=COUNTIF({bd}!{BOARD_DCOL}:{BOARD_DCOL},"{QUAL_LABEL}")'),
    ('Qualified Conversations', sum_all()),
    ('ACTIVITY',              ''),
    ('Meetings',              sum_booked()),
    ('Conversations',         sum_all()),
    ('QUALITY',               ''),
    ('Show Rate',             f'=IFERROR(COUNTIF({bd}!{BOARD_ECOL}:{BOARD_ECOL},"{SHOW_LABEL}")/COUNTA({bd}!{BOARD_ECOL}2:{BOARD_ECOL}),"—")'),
    ('Score',                 f'=IFERROR(ROUND(AVERAGE({bd}!{BOARD_FCOL}2:{BOARD_FCOL}),1),"—")'),
    ('BREAKDOWN',             ''),
    ('Meeting Scheduled',     sum_dispo('Meeting Scheduled')),
]

# Fetch Meeting Board showed counts per rep once (for effective-rate ranking)
_board_rows = svc.spreadsheets().values().get(
    spreadsheetId=sid,
    range=f"'{BOARD_TAB}'!{BOARD_ECOL}2:{BOARD_ICOL}2000").execute().get('values', [])
_board_showed = {}
_ecol_idx = BOARD_REP - BOARD_SHOW  # offset within the fetched range
for _r in _board_rows:
    if _r and str(_r[0]).strip() == SHOW_LABEL and len(_r) > _ecol_idx:
        _rn = str(_r[_ecol_idx]).strip()
        if _rn: _board_showed[_rn] = _board_showed.get(_rn, 0) + 1

def live_rep_effective_rate(rep):
    try:
        r = svc.spreadsheets().values().get(
            spreadsheetId=sid, range=f"'{rep}'!{REP_FCOL}2:{REP_FCOL}").execute()
        convos = sum(1 for row in r.get('values', []) if row and row[0].strip())
        return _board_showed.get(rep, 0) / convos if convos else 0.0
    except Exception:
        return 0.0

def rep_effective_rate(rep):
    showed = (f"COUNTIFS('{BOARD_TAB}'!{BOARD_ECOL}:{BOARD_ECOL},\"{SHOW_LABEL}\","
              f"'{BOARD_TAB}'!{BOARD_ICOL}:{BOARD_ICOL},\"{rep}\")")
    convos = f"COUNTA('{rep}'!{REP_FCOL}2:{REP_FCOL})"
    return f'=IFERROR(TEXT({showed}/{convos},"0.0%"),"—")'

rep_counts  = {rep: live_rep_effective_rate(rep) for rep in REPS}
REPS_RANKED = sorted(REPS, key=lambda r: rep_counts[r], reverse=True)

try:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo('America/Phoenix')
except Exception:
    tz = timezone.utc
now = datetime.now(tz)
stamp = (f'Updated: {now.strftime("%B %d, %Y at %I:%M%p")}'
         .replace(' 0', ' ').replace('AM', 'am').replace('PM', 'pm'))

rows = []

# Row 1 — timestamp (merged A1:J1)
rows.append([stamp])

# Row 2 — section headers
rows.append(['Statistics', '=CELL("sheet",$A$1)', '', 'ICP Report', '', '', '', '', '10-Week Overview', ''])

# Row 3 — column headers
rows.append(['OUTCOMES', '', '', 'Title', 'Meetings', 'Activated', 'Nurture', '', 'Week', 'Meetings'])

# Rows 4-13 — 9 named ICP personas; row 13 ICP section left blank
for i, (a_row, icp_row) in enumerate(zip_longest(A_COL_4_13, ICP, fillvalue=None)):
    a_label, a_formula = a_row
    if icp_row:
        icp_label, patterns = icp_row[0], icp_row[1]
        d_icp  = icp_label
        d_mtgs = icp_meetings(patterns)
        d_act  = icp_dispo(patterns, ACT_DISPO)
        d_nur  = icp_dispo(patterns, NUR_DISPO)
    else:
        d_icp = d_mtgs = d_act = d_nur = ''
    rows.append([a_label, a_formula, '', d_icp, d_mtgs, d_act, d_nur, '', week_label(i), week_meetings(i)])

# Row 14 — Rep Breakdown + Leaderboard headers
rows.append(['Meeting Confirmed', sum_dispo('Meeting Confirmed'), '',
             'Rep Breakdown', '', '', '', '', 'Leaderboard', ''])

# Row 15 — sub-headers
rows.append([
    'Rescheduled',
    sum_dispo('Rescheduled') + '+' + sum_dispo('Needs Rescheduled').lstrip('='), '',
    'Rep', 'Meetings', 'Activated', 'Nurture', '', 'Name', 'Eff. Rate'
])

# Rows 16-20 — disposition breakdown + rep stats
DISPOS_16_20 = cfg.get('overall_stats', {}).get('breakdown_dispos',
    ['Not Interested', 'Activated Lead', 'Nurture', 'Referred Outward', 'Not Me'])
for dispo, rep in zip(DISPOS_16_20, REPS_RANKED):
    rows.append([
        dispo, sum_dispo(dispo), '',
        rep, rep_booked(rep), rep_dispo(rep, ACT_DISPO), rep_dispo(rep, NUR_DISPO), '',
        rep, rep_effective_rate(rep)
    ])

# Row 21 — Not Now + footer
rows.append(['Not Now', sum_dispo('Not Now'), '',
             '*Score = Meetings×60 + Activated×30 + Nurture×10', '', '', '', '', '', ''])

svc.spreadsheets().values().update(
    spreadsheetId=sid,
    range=f"'{STATS_TAB}'!A1:J21",
    valueInputOption='USER_ENTERED',
    body={'values': rows}
).execute()

svc.spreadsheets().values().update(
    spreadsheetId=sid,
    range=f"'{STATS_TAB}'!I21",
    valueInputOption='USER_ENTERED',
    body={'values': [['*Eff. Rate = showed ÷ convos — goal: 5% (10% booked × 50% shown)']]}
).execute()

ranked_str = ', '.join(f"{r.split()[0]} {rep_counts[r]:.1%}" for r in REPS_RANKED)
print(f'Overall Statistics rebuilt — ICP (wildcard) + 10-week + reps ({ranked_str}).')
