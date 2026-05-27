# Skill: Pre-Brief Notes v1

Auto-generate a one-page pre-meeting brief from the call that booked a meeting, and
drop a clickable `View` link into a "Pre-Brief" column on a meetings board.

Pairs with **Master Tracker v2** / a Meeting Board that already has a call recording per row.

## What it does

For each board row that has a call recording but no pre-brief yet:
1. Pulls the call's transcript (Deepgram → Groq fallback) from the recording link
2. Asks Claude for the bullets that matter going into the meeting — the prospect's
   concerns, questions, objections, asks, priorities, and any commitments made
3. Builds a Google Doc: the bullets on page 1, the full transcript on page 2, with each
   bullet anchored to the transcript line it came from
4. Writes a blue `=HYPERLINK(...,"View")` into the Pre-Brief column

Idempotent: skips rows that already have a pre-brief link. Stops cleanly if the host
Claude plan's usage window is hit; a cron picks up the rest next run.

## Setup

1. `config.template.json` → `config.json`; set `sheet_id`, `board_tab`, and the 1-indexed
   `columns` (prospect / company / prebrief / recording / rep) for your board layout.
2. Add a "Pre-Brief" column to your board (any position — point `columns.prebrief` at it).
3. Drop credentials in this folder (gitignored): `google_token.json` (OAuth, Drive+Sheets),
   `client_secret.json`, and `_trellus.json` (`{"api_key","team_id"}`).
4. Put `GROQ_API_KEY` (and/or `DEEPGRAM_API_KEY`) in a local `.env`.

## Run

```
python3 prebrief.py                       # fill all rows missing a brief
PREBRIEF_ONLY=acme python3 prebrief.py    # one prospect/company
PREBRIEF_LIMIT=2 python3 prebrief.py      # cap this run
```

Cron-safe. The recording link format expected is a Trellus `session_id=` URL; adapt
`fetch_segments` if your recordings live elsewhere.

## Files
- `prebrief.py` — the whole engine (transcribe → bullets → doc → link)
