# RevCentric Skills

Three reusable sales-automation skills that turn Apollo call activity into a maintained
Google Sheet, tailored per-prospect decks, and one-page meeting pre-briefs. Each is
**config-driven** (no org details hardcoded) and ships with a `.gitignore` so credentials
never get committed. Copy `config.template.json` → `config.json` per skill and fill it in.

They chain together but each runs standalone:

```
Apollo calls ──[Master Tracker v2]──▶ rep tabs in a Google Sheet
                                          │
                          ┌───────────────┴───────────────┐
                          ▼                                ▼
                 [Custom Decks v2]                 [Pre-Brief Notes v1]
            tailored deck per prospect        one-page brief per booked meeting
```

## Skills

### 1. [Master Tracker v2](./master-tracker-v2)
Pulls phone calls from Apollo into per-rep tabs of a Google Sheet, filtered to the
dispositions you care about. The engine that feeds the other two skills.
**Key fix:** a call is only marked ingested *after* it's written to the sheet, so calls
a rep tags *after* the dialer logs them (the common case) still get picked up.

### 2. [Custom Decks v2](./custom-decks-v2)
For each tracked prospect, transcribes the call, scrapes their site, and has Claude write
deck copy specific to *that* company — then renders Slides + PDF and drops a `View` link
into a "Custom Decks" tab. Refuses to ship generic boilerplate.

### 3. [Pre-Brief Notes v1](./prebrief-notes-v1)
For each booked meeting, turns the call that booked it into a one-page Google Doc: the
bullets that matter going in (concerns, objections, asks, commitments), each anchored to
the transcript line it came from. Drops a `View` link into a "Pre-Brief" column.

## Setup (shared)

All three need:
- **Google OAuth** (`google_token.json` + `client_secret.json`) with Sheets — plus Drive +
  Slides for the deck/pre-brief skills. Gitignored.
- **Apollo API key** (Master Tracker) and **transcription keys** in a local `.env`:
  `DEEPGRAM_API_KEY` (primary) and/or `GROQ_API_KEY` (fallback).
- Optional **Trellus** (`_trellus.json`) to mint public call-recording links.

Transcription uses Deepgram first, Groq as fallback — Groq has a low daily audio cap, so
Deepgram carries the load when available. See each skill's `SKILL.md` for specifics.

## Notes
- All scripts are cron-safe and idempotent (append-only sheet writes, lockfiles where needed).
- Throughput for deck/pre-brief generation is bounded by your Claude plan's usage window
  and your transcription quota — large batches drain over time via cron, not all at once.
