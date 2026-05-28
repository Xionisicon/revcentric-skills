#!/usr/bin/env python3
"""Create a blank master-tracker Google Sheet ready for the three organs to plug into.

Creates a new Google Spreadsheet with:
  - Meeting Board tab (headers, no data)
  - N rep tabs named "Rep Name" by default (rename after creation)
  - Custom Decks tab (headers, no data)
  - Overall Statistics tab (populated by overall_stats.py after first import)

No data, no code, no existing names. Just the skeleton.

Usage:
  python3 create_blank_tracker.py                    # 5 rep tabs (RC default)
  python3 create_blank_tracker.py --reps 3           # 3 rep tabs
  python3 create_blank_tracker.py --name "My Tracker" --reps 4
  SKILL_CONFIG=./config.json python3 create_blank_tracker.py
"""
import argparse
import json
import os
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
svc    = build('sheets', 'v4', credentials=creds)
drive  = build('drive',  'v3', credentials=creds)

p = argparse.ArgumentParser()
p.add_argument('--name', default='Master Tracker (blank)', help='Sheet title')
p.add_argument('--reps', type=int, default=5, help='Number of rep tabs (default 5)')
args = p.parse_args()

REP_PLACEHOLDER = 'Rep Name'

# Tab definitions: (title, [header row])
REP_HEADERS  = ['Date', 'Prospect', 'Company', 'Title', 'Recording', 'Disposition',
                'Correct Disposition', '', '']
BOARD_HEADERS= ['Date', 'Prospect', 'Company', 'Qualification', 'Show Status', 'Score',
                'Pre-Brief', 'Recording', 'Rep']
DECKS_HEADERS= ['Date', 'Prospect', 'Company', 'Website', 'Email', 'Deck', 'Status', 'Rep']

tabs = (
    [('Meeting Board', BOARD_HEADERS)]
    + [(REP_PLACEHOLDER, REP_HEADERS)] * args.reps
    + [('Custom Decks', DECKS_HEADERS),
       ('Overall Statistics', [])]
)

# 1. Create the spreadsheet with all tabs in one call
sheet_body = {
    'properties': {'title': args.name},
    'sheets': [{'properties': {'title': title}} for title, _ in tabs],
}
result = svc.spreadsheets().create(body=sheet_body, fields='spreadsheetId,sheets.properties').execute()
sid = result['spreadsheetId']
sheets = {s['properties']['title']: s['properties']['sheetId'] for s in result['sheets']}

print(f'Created: https://docs.google.com/spreadsheets/d/{sid}')

# 2. Write headers to each tab
requests = []
for title, headers in tabs:
    if not headers:
        continue
    # Find sheet ID — tabs with same name get a suffix in the API response; handle duplicates
    # by using the first unmatched one
    sheet_id = sheets.get(title)
    if sheet_id is None:
        continue
    # Write header row as values
    svc.spreadsheets().values().update(
        spreadsheetId=sid,
        range=f"'{title}'!A1",
        valueInputOption='USER_ENTERED',
        body={'values': [headers]},
    ).execute()

# 3. Bold + freeze the header row on all data tabs, set default column widths
bold_freeze_requests = []
for title, headers in tabs:
    if not headers:
        continue
    sheet_id = sheets.get(title)
    if sheet_id is None:
        continue
    bold_freeze_requests += [
        # Bold header row
        {
            'repeatCell': {
                'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1},
                'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
                'fields': 'userEnteredFormat.textFormat.bold',
            }
        },
        # Freeze header row
        {
            'updateSheetProperties': {
                'properties': {'sheetId': sheet_id, 'gridProperties': {'frozenRowCount': 1}},
                'fields': 'gridProperties.frozenRowCount',
            }
        },
    ]

if bold_freeze_requests:
    svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={'requests': bold_freeze_requests}).execute()

print(f'\nTabs created:')
for title, _ in tabs:
    print(f'  {title}')
print(f'\nNext steps:')
print(f'  1. Rename the "{REP_PLACEHOLDER}" tabs to your reps\' names')
print(f'  2. Copy config.json from master-tracker-v2, set sheet_id = {sid}')
print(f'  3. Run: python3 apollo_pull.py       (imports calls into rep tabs)')
print(f'  4. Run: python3 overall_stats.py     (populates the stats tab)')
print(f'  5. Configure Custom Decks v2 and Pre-Brief v1 with the same sheet_id')
print(f'\nSheet URL: https://docs.google.com/spreadsheets/d/{sid}')
