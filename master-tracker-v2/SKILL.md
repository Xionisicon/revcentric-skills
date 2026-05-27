# Skill: Master Tracker v2

Import call activity from Apollo into a Google Sheet, one tab per rep, filtered to the
dispositions a team cares about. This is the engine that feeds downstream boards
(Custom Decks, Meeting Board, Pre-Brief).

## What it does

For each rep, pulls recent `/phone_calls/search` results from Apollo, keeps only the
configured dispositions, and appends new calls to that rep's tab. Optionally mints
public call-recording links (Trellus) and auto-fills a "Correct Disposition" review
column for historical rows.

## Why v2

v1 added **every** call ID it saw to a permanent skip list. Reps usually tag a call's
disposition *after* the dialer logs it, so the first pull saw a blank disposition,
skipped it, and burned the ID — meaning the call never came in even once it was tagged.

v2 only records a call ID as *ingested* once it is **successfully written** to a rep tab.
Calls that are pulled but not written (e.g., deduped or missing contact info) are
re-checked every run inside a rolling window (`backfill_days`). Late-tagged and
enriched calls now get picked up automatically.

## Setup

1. Copy `config.template.json` → `config.json` and fill in:
   - `apollo_api_key` — an Apollo master key with phone-call access
   - `google.sheet_id` — the target sheet
   - `google.oauth_token_file` / `client_secret_file` — Google OAuth (Sheets scope)
   - `reps` — map of `"Rep Display Name": "apollo_user_id"`. Each name must match a tab.
   - `keep_dispositions` — exact disposition labels to import
   - `keep_disposition_prefixes` — e.g. `["Not Interested"]` keeps `Not Interested - X` variants verbatim
   - `backfill_days` — rolling window re-scanned each run (30 is typical)
   - `autofill_correct_disposition_through` — date (YYYY-MM-DD) before which col G is
     auto-filled from col F; after it, col G is left blank for human review. Empty = never autofill.
   - `trellus` — optional; set `api_key`/`team_id` to mint public recording links
2. Create one tab per rep, named exactly as in `reps`, with this header row:
   `Date | Prospect | Company | Title | Recording | Disposition | Correct Disposition | (free) | (free)`

## Run

```
python3 apollo_pull.py            # uses ./config.json
MT_CONFIG=/path/config.json python3 apollo_pull.py
```

Idempotent and safe to cron (e.g. every 30 min). It only appends new rows and never
rewrites existing ones, so manual edits to columns G/H/I are preserved.

## Routing (downstream)

Rows route to downstream boards by their **actual disposition (col F)**, not the
reviewed col G:
- Custom Decks ← Activated Lead, Meeting Scheduled, Nurture, Connect Incomplete - Send Propaganda
- Meeting Board ← Meeting Scheduled, Meeting Confirmed, Rescheduled

See the **Custom Decks v2** and **Pre-Brief Notes v1** skills for those engines.

## Notes
- Uses a browser User-Agent; some WAFs block default Python UAs on Apollo/Trellus.
- 429s are handled with `retry-after`-aware exponential backoff.
- State lives in `state.json` (list of ingested call IDs). Delete it to force a full re-scan of the window.
