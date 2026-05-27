#!/usr/bin/env python3
"""Personalize a single deck via the Claude CLI.

Reads the existing tokens file, pulls website content + transcript, sends to
`claude -p` with a structured prompt, gets per-token JSON back, validates it,
writes back, and re-renders the deck in place.

Usage:
  python3 rc_deck_personalize.py --tokens /path/to/{slug}_tokens.json \
      --slides-id <Drive ID> \
      [--website https://example.com] [--transcript "raw text"]

Designed for use both as a standalone fixer and inside rc_deck_queue_cron.py.
"""
import os
import argparse, json, os, re, subprocess, sys, requests
from urllib.parse import urlparse

REQUIRED_KEYS = [
    'SLIDE1_HOOK',
    'SHIFT_HEADLINE','SHIFT_PUNCHLINE','SHIFT_BODY',
    'SHIFT_STAT1_NUM','SHIFT_STAT1_HEAD','SHIFT_STAT1_BODY',
    'SHIFT_STAT2_NUM','SHIFT_STAT2_HEAD','SHIFT_STAT2_BODY',
    'SHIFT_STAT3_NUM','SHIFT_STAT3_HEAD','SHIFT_STAT3_BODY',
    'SHIFT_CLOSE',
    'COMPETE_HEAD1','COMPETE_HEAD2','COMPETE_INTRO',
    'COMPETITOR_NAME','COMPETITOR_TAGLINE',
    'COMPETITOR_LINE1','COMPETITOR_LINE2','COMPETITOR_LINE3',
    'COMPANY_TAGLINE','COMPANY_LINE1','COMPANY_LINE2','COMPANY_LINE3',
    'WHY_OUTBOUND_FITS','ICP_LABEL','THEIR_TARGET_TITLE',
]

SCRAPE_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
SUBPAGE_PATHS = ['', '/about', '/about-us', '/product', '/products', '/solutions',
                 '/platform', '/customers', '/case-studies', '/pricing']

def _scrape_one(url, char_cap=4000):
    try:
        r = requests.get(url, timeout=10, headers={'User-Agent': SCRAPE_UA},
                         allow_redirects=True)
        if not r.ok: return ''
        html = r.text
        html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.S|re.I)
        html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.S|re.I)
        html = re.sub(r'<nav[^>]*>.*?</nav>', ' ', html, flags=re.S|re.I)
        html = re.sub(r'<footer[^>]*>.*?</footer>', ' ', html, flags=re.S|re.I)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:char_cap]
    except Exception:
        return ''

def fetch_site_text(url, char_cap=10000):
    """Pull a website's visible text across home + a few common subpages."""
    if not url: return ''
    url = url.rstrip('/')
    base = url
    # Strip path if it has one — we want the root + subpaths
    m = re.match(r'^(https?://[^/]+)', url)
    if m: base = m.group(1)
    parts = []
    seen = set()
    for path in SUBPAGE_PATHS:
        u = base + path if path else base
        if u in seen: continue
        seen.add(u)
        t = _scrape_one(u, char_cap=2400)
        if t and len(t) > 200:
            parts.append(f'--- {u} ---\n{t}')
        if sum(len(p) for p in parts) >= char_cap:
            break
    return '\n\n'.join(parts)[:char_cap]

PROMPT_TEMPLATE = '''You are writing slide tokens for a RevCentric prospect deck.

RevCentric runs done-for-you outbound for B2B companies. We bring the SDR team, the dialer, the lists, and the call coaching. We focus on meaningful, completed conversations and accountable outcomes for our clients.

**LANGUAGE RULES — read carefully:**
- NEVER mention "pay per meeting", "qualified meeting", "billed per meeting", "performance-based pricing", "no meetings no invoice", or any phrase that reveals the commercial model.
- NEVER cite specific close rates, conversion rates, or pricing details.
- Frame outcomes generally: "meaningful conversations", "accountable to outcomes", "transparent on every dial", "we own the result".
- The specific pricing model is reserved for the prospect's actual sales call. The deck only hints at outcome-orientation; never gives the mechanic away.

VOICE — write like Lara Acosta:
- Short, punchy sentences. Max 12 words each.
- Every sentence is its own complete thought.
- One concrete idea per line. No hedging, no run-ons, no "in order to".
- Specific numbers and names beat abstract claims.
- No em-dashes back-to-back, no double-hyphens, no "—" overuse.
- Sound like a smart human wrote it in one pass, not a template.

**SPECIFICITY — this is the most important rule:**
The deck must read like RevCentric researched THIS company. Most of our decks fail because they're generic outbound-pitch wallpaper. Read the website carefully and pull at LEAST 3 concrete signals to weave through the copy:
- An actual product name or feature THEY ship (not "their platform" — the real name)
- An ICP detail THEY claim on their site (industry, buyer title, geography, deal size)
- A customer logo, case study, integration partner, or named competitor THEY mention
- A technical claim, stat, or differentiator THEY make (in their words, paraphrased)
- A recent move (funding, hire, launch, rebrand, expansion) if surfaced in transcript or site

If the website said "we automate AR for mid-market SaaS finance teams" — your deck must reflect AR, mid-market, SaaS finance, NOT generic "B2B teams". Use the company's own vocabulary. Where the transcript gave you a specific pain (slow ramp, bad list, wrong rep, integration broke), name it.

ALWAYS produce the deck. Use whatever signal you have — even just the company name + what they broadly do is enough to write copy that names their space and buyer. Do NOT fall back to "they don't Google you" wallpaper; write about THEM at whatever fidelity the inputs allow. Only output the literal string `INSUFFICIENT_SIGNAL` (instead of JSON) in the rare case where you cannot even tell what the company does at all. Do not invent specific stats, customer names, or funding you weren't given.

PROSPECT: {first_name} {last_name}
COMPANY: {company}
COMPANY WEBSITE: {website}

WHAT THE WEBSITE SAYS (multi-page scrape, sectioned by URL):
{website_text}

CALL TRANSCRIPT (may be partial / imperfect):
{transcript}

Show that you understand THEIR business, THEIR space, and why outbound fits THEM specifically. Name a real competitor (a real one — use the website / transcript signal, not a generic placeholder). If the transcript reveals pain, weave it in naturally — never paste raw transcript snippets.

For every multi-line token (SHIFT_BODY, COMPETE_INTRO, WHY_OUTBOUND_FITS), put EACH sentence on its own line by separating with `<br>`. Never have two sentences on the same line.

For STAT bodies (SHIFT_STAT1_BODY through SHIFT_STAT3_BODY): ≤8 words total, ONE short sentence each. These render in a narrow box — anything longer cuts off.

Output JSON ONLY (no markdown fences, no commentary). Every key below is required. Honor the character budgets — they are HARD caps, not guidelines.

{{
  "SLIDE1_HOOK": "<=60 chars / max 8 words. ONE line. Slide 1 title — about THEM only. Their tagline, their bet, their state. NO mention of RevCentric, outbound, SDRs, or pipeline. Pull from website signal. Example for an AR-AI company: 'Get paid on time. Every time.' Example for a GPU marketplace: 'Compute, on tap.' If you can't write it from their own signal, output INSUFFICIENT_SIGNAL.",
  "SHIFT_HEADLINE": "<=38 chars / max 6 words. ONE line on the slide, never wraps. Punchy headline only.",
  "SHIFT_PUNCHLINE": "<=38 chars / max 6 words. ONE line on the slide. The bold counter-punch.",
  "SHIFT_BODY": "<=220 chars, 3-4 sentences separated by <br>. Each sentence is its own complete thought. No sentence longer than 12 words.",
  "SHIFT_STAT1_NUM": "<=8 chars, a real or directionally-true stat",
  "SHIFT_STAT1_HEAD": "<=22 chars",
  "SHIFT_STAT1_BODY": "<=60 chars, ONE short sentence. Max 8 words.",
  "SHIFT_STAT2_NUM": "<=8 chars",
  "SHIFT_STAT2_HEAD": "<=22 chars",
  "SHIFT_STAT2_BODY": "<=60 chars, ONE short sentence. Max 8 words.",
  "SHIFT_STAT3_NUM": "<=8 chars",
  "SHIFT_STAT3_HEAD": "<=22 chars",
  "SHIFT_STAT3_BODY": "<=60 chars, ONE short sentence. Max 8 words.",
  "SHIFT_CLOSE": "<=140 chars, 1-2 sentences max, each on its own line via <br>",
  "COMPETE_HEAD1": "<=38 chars / max 6 words. ONE line, never wraps.",
  "COMPETE_HEAD2": "<=38 chars / max 6 words. ONE line, the bold counter-punch.",
  "COMPETE_INTRO": "<=200 chars, 2-3 sentences separated by <br>. Name the competitor.",
  "COMPETITOR_NAME": "<=30 chars, real competitor brand",
  "COMPETITOR_TAGLINE": "<=55 chars, in quotes",
  "COMPETITOR_LINE1": "<=55 chars",
  "COMPETITOR_LINE2": "<=55 chars",
  "COMPETITOR_LINE3": "<=55 chars",
  "COMPANY_TAGLINE": "<=55 chars, in quotes",
  "COMPANY_LINE1": "<=55 chars",
  "COMPANY_LINE2": "<=55 chars",
  "COMPANY_LINE3": "<=55 chars",
  "WHY_OUTBOUND_FITS": "<=180 chars, 2-3 SHORT sentences separated by <br>. Each one its own line. Be punchy, no fluff.",
  "ICP_LABEL": "<=45 chars",
  "THEIR_TARGET_TITLE": "<=35 chars"
}}

Output ONLY the JSON. No prose before or after.'''

CLAUDE_BIN = '/usr/bin/claude'

def call_claude(prompt, timeout=300, retries=1):
    """Send prompt to claude CLI, return stdout. Retries once on timeout."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            res = subprocess.run([CLAUDE_BIN,'-p',prompt],
                capture_output=True, text=True, timeout=timeout)
            if res.returncode != 0:
                raise RuntimeError(f'claude CLI failed: {res.stderr[-400:]}')
            return res.stdout.strip()
        except subprocess.TimeoutExpired as e:
            last_err = e
            if attempt < retries:
                print(f'  claude timeout (attempt {attempt+1}); retrying…', flush=True)
                continue
            raise

def extract_json(s):
    """Pull a JSON object out of Claude output, tolerant of prose + fences."""
    s = s.strip()
    # Strip markdown code-fences anywhere in the output
    s = re.sub(r'```(?:json)?', '', s)
    # Find the largest {...} block by scanning for the first { and matching braces
    start = s.find('{')
    if start < 0:
        raise ValueError(f'no JSON object in claude output: {s[:300]}')
    depth = 0
    for i in range(start, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return json.loads(s[start:i+1])
    raise ValueError(f'unmatched braces in claude output: {s[start:start+300]}')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tokens', required=True)
    p.add_argument('--slides-id', required=True)
    p.add_argument('--website', default='')
    p.add_argument('--transcript', default='')
    p.add_argument('--render', action='store_true', help='Re-render the deck after personalizing')
    args = p.parse_args()

    with open(args.tokens) as f: tokens = json.load(f)

    company = tokens.get('COMPANY_NAME','')
    first_name = tokens.get('FIRST_NAME','')
    last_name = ''
    # Try to recover last name from any context
    # (full name not in tokens; caller can ignore if blank)

    website = args.website or tokens.get('_WEBSITE','') or ''
    transcript = args.transcript or ''
    website_text = fetch_site_text(website) if website else ''
    # Truncate transcript so prompt stays sane
    transcript = transcript[:4000]

    prompt = PROMPT_TEMPLATE.format(
        first_name=first_name, last_name=last_name, company=company,
        website=website or '(none)',
        website_text=website_text or '(none)',
        transcript=transcript or '(none)',
    )

    print(f'→ {company} — calling Claude (website={len(website_text)}c, transcript={len(transcript)}c)…', flush=True)
    raw = call_claude(prompt)
    try:
        gen = extract_json(raw)
    except Exception as e:
        print(f'  parse error: {e}', file=sys.stderr)
        print(f'  raw: {raw[:500]}', file=sys.stderr)
        sys.exit(2)

    missing = [k for k in REQUIRED_KEYS if k not in gen]
    if missing:
        print(f'  MISSING keys in claude output: {missing}', file=sys.stderr)
        sys.exit(3)

    # Merge in (don't overwrite anything outside REQUIRED_KEYS like SENDER_*, BOOKING_LINK)
    for k in REQUIRED_KEYS:
        v = gen.get(k, '')
        if isinstance(v, (int, float)): v = str(v)
        tokens[k] = v

    with open(args.tokens, 'w') as f:
        json.dump(tokens, f, indent=2)
    print(f'  tokens written: {args.tokens}', flush=True)

    if args.render:
        cmd = ['python3', os.path.join(os.path.dirname(os.path.abspath(__file__)),'render_deck.py'),
               '--tokens', args.tokens, '--slides-id', args.slides_id]
        rr = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if rr.returncode != 0:
            print(f'  render FAILED: {rr.stderr[-400:]}', file=sys.stderr)
            sys.exit(4)
        print(f'  rendered ok', flush=True)

if __name__ == '__main__':
    main()
