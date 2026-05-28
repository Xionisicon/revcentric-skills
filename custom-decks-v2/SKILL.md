# Skill: Custom Decks v2

One organ of the system. Takes every activated lead from the master tracker and builds a
tailored, company-specific deck for each one — automatically — dropping a `View` link into
a "Custom Decks" tab. The deck reads researched, not templated: real signals from their
website, call transcript, and ICP are baked in.

Pairs with **Master Tracker v2** (the body) and shares the same Google Sheet.

## What it does

1. `custom_decks_sync.py` — scans rep tabs, finds rows whose **disposition (col F)** is
   one of `deck_source_dispositions`, dedups by prospect+company, enriches website/email
   from Apollo, and writes them into the Custom Decks tab (one row per prospect, deck cell blank).
2. `deck_queue.py` — for each Custom Decks row missing a deck:
   - finds the source call in the rep tabs (cached in one read)
   - transcribes the recording (Deepgram → Groq fallback)
   - scrapes the prospect's website across several pages
   - calls Claude to write deck copy that is specific to THAT company
   - renders the deck (Slides + PDF) via `render_deck.py` and writes a `View` link into the row
   - self-checks the result and refuses to ship generic "wallpaper" copy

## Why v2

- **Specificity guard:** the personalize prompt forces real signals (their product, ICP,
  competitor, funding) and only bails (`INSUFFICIENT_SIGNAL`) when the company can't be
  identified at all — so decks read researched, not templated.
- **Re-render in place:** rebuilding a deck reuses its existing Slides ID, so a deck URL
  never goes blank mid-rebuild.
- **Throughput:** rep tabs are read once per run (not per deck), and `claude -p` calls
  tolerate concurrency — a bundled rebuild driver can run several at once. Note the host
  Claude plan's usage window caps how many decks build per burst; the cron drains the rest.

## Setup

1. `config.template.json` → `config.json`; fill `sheet_id`, `reps`, `deck_source_dispositions`,
   `booking_link`.
2. Drop credentials in this folder (all gitignored): `google_token.json` (OAuth with
   Drive+Sheets+Slides), `client_secret.json`, and `_trellus.json` (`{"api_key","team_id"}`)
   if you mint Trellus recording links.
3. Put transcription keys in a local `.env`: `DEEPGRAM_API_KEY=...` and/or `GROQ_API_KEY=...`.
4. **Make it yours:** the deck identity is RevCentric by default. Edit `deck_template.md.tpl`
   (your brand, colors, slide copy) and the `PROMPT_TEMPLATE` seller paragraph in
   `personalize.py` to your company's name + pitch.
5. Create a "Custom Decks" tab with header:
   `Date | Prospect | Company | Website | Email | Deck | Status | Rep`

## Run

```
python3 custom_decks_sync.py      # rep tabs -> Custom Decks rows
python3 deck_queue.py             # build decks for rows missing one
DECK_PRIORITY=acme python3 deck_queue.py   # build a specific prospect first
```

Both are cron-safe. `deck_queue.py` holds a lockfile so overlapping runs don't race.

## Files
- `custom_decks_sync.py` — rep tabs → Custom Decks rows (config-driven)
- `deck_queue.py` — builds decks for blank rows
- `personalize.py` — website scrape + transcript → Claude → deck tokens (edit seller pitch here)
- `render_deck.py` — tokens + template → Slides/PDF on Drive
- `deck_template.md.tpl` / `template_tokens.json` — the deck design (swap for your brand)
