---
marp: true
theme: default
paginate: false
size: 16:9
style: |
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
  :root {
    --bg: #fafaf9;
    --bg-warm: #fff7ef;
    --fg: #0d0d0d;
    --fg-soft: #2b2b2b;
    --muted: #6b6b6b;
    --line: rgba(13,13,13,0.10);
    --brand-1: #fe811e;
    --brand-2: #fd5235;
    --brand-3: #fd2c48;
  }
  section {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--fg);
    padding: 44px 72px 52px 72px;
    font-size: 22px;
    line-height: 1.45;
    font-weight: 400;
    letter-spacing: -0.01em;
    position: relative;
    overflow: hidden;
    background-image: url('/root/Sonny/decks/assets/rc_logo.png');
    background-repeat: no-repeat;
    background-position: top 28px right 36px;
    background-size: 38px 38px;
  }
  h1, h2, h3, h4, h5, h6 { border: none !important; text-decoration: none !important; }
  h1 { font-weight: 900; font-size: 50px; letter-spacing: -0.02em; line-height: 1.04; margin: 0 0 18px; text-transform: uppercase; }
  h1 + h1, h1 + h2, h2 + h2 { margin-top: -14px; }
  h2 { font-weight: 800; font-size: 50px; letter-spacing: -0.02em; line-height: 1.04; margin: 0 0 16px; text-transform: uppercase; }
  h3 { font-weight: 600; font-size: 13px; letter-spacing: 0.22em; text-transform: uppercase; color: var(--muted); margin: 0 0 14px; }
  p { font-size: 21px; line-height: 1.3; margin: 0 0 10px; color: var(--fg-soft); }
  p br { line-height: 1.2; }
  ul { font-size: 20px; line-height: 1.55; padding-left: 22px; margin: 0 0 12px; }
  li { margin-bottom: 6px; }
  a { text-decoration: none !important; border: none !important; }
  strong, .grad, .huge, .metric, .col h3, .auth-card .metric {
    text-decoration: none !important;
    border: none !important;
  }
  strong {
    color: var(--brand-2);
    font-weight: 700;
    background: none;
  }
  em { color: var(--muted); font-style: normal; }
  blockquote {
    border-left: 4px solid;
    border-image: linear-gradient(180deg, var(--brand-1), var(--brand-3)) 1;
    padding: 6px 0 6px 22px;
    color: var(--fg);
    font-size: 22px; font-weight: 500; line-height: 1.4;
    font-style: normal; margin: 0;
  }
  table { border-collapse: collapse; width: 100%; font-size: 18px; }
  th { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--line); color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; font-size: 11px; }
  td { padding: 12px 14px; border-bottom: 1px solid var(--line); color: var(--fg-soft); }
  hr { display: none; }

  .grad { color: var(--brand-2); background: none; }
  .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.24em; color: var(--brand-2); font-weight: 700; margin-bottom: 22px; }
  .huge { font-size: 160px; font-weight: 900; letter-spacing: -0.06em; line-height: 0.88; color: var(--brand-2); }
  .footer { position: absolute; bottom: 22px; left: 80px; right: 80px; display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); letter-spacing: 0.18em; text-transform: uppercase; font-weight: 600; }
  .row { display: flex; gap: 22px; margin-top: 18px; }
  .col { flex: 1; padding: 20px 22px; border: 1px solid var(--line); border-radius: 12px; background: #ffffff; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
  .col h3 { color: var(--brand-2); font-size: 11px; }
  .col p { font-size: 15px; line-height: 1.3; margin: 0 0 6px; }

  .blob { position: absolute; border-radius: 50%; filter: blur(120px); opacity: 0.18; pointer-events: none; z-index: 0; }
  .blob-1 { width: 380px; height: 380px; background: var(--brand-1); top: -180px; right: -160px; }
  .blob-2 { width: 320px; height: 320px; background: var(--brand-3); bottom: -200px; left: -180px; opacity: 0.14; }
  .grid { position: absolute; inset: 0; background-image: radial-gradient(rgba(13,13,13,0.06) 1px, transparent 1px); background-size: 28px 28px; pointer-events: none; mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%); }

  .vs-row { display: flex; gap: 20px; margin-top: 18px; }
  .vs-col { flex: 1; padding: 22px 24px; border-radius: 14px; }
  .vs-col h4 { font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase; margin: 0 0 12px; font-weight: 700; }
  .vs-col p { font-size: 15px; margin: 0 0 8px; line-height: 1.5; }
  .winner { background: linear-gradient(135deg, rgba(254,129,30,0.12), rgba(253,44,72,0.06)); border: 1px solid rgba(253,82,53,0.30); }
  .winner h4 { color: var(--brand-2); }
  .loser { background: #ffffff; border: 1px solid var(--line); }
  .loser h4 { color: var(--muted); }

  /* Title slide */
  section.title {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
  }
  section.title h1, section.title p, section.title .label {
    text-align: center;
  }
  section.title .title-row {
    display: inline-flex;
    align-items: flex-end;
    justify-content: center;
    gap: 28px;
    margin-bottom: 32px;
    line-height: 0;
  }
  section.title .title-row img { vertical-align: bottom; margin: 0 !important; padding: 0 !important; max-width: none !important; max-height: none !important; }
  section.title .title-row .title-mark { margin: 0 !important; padding: 0 !important; }
  span, span.grad { border: none !important; outline: none !important; box-shadow: none !important; }
  .avatar-wrap { width: 72px; height: 72px; border-radius: 50%; overflow: hidden; margin: 0 auto 10px; display: block; }
  .avatar-wrap img { width: 72px !important; height: 72px !important; max-width: 72px !important; min-width: 72px !important; object-fit: cover; display: block; border-radius: 50%; }
  .stat-num { font-size: 40px; font-weight: 800; color: #fd5235 !important; line-height: 1; margin-bottom: 6px; display: block; }
  .stat-word { font-size: 44px; font-weight: 800; color: #fd5235 !important; line-height: 1; margin-bottom: 8px; display: block; }

  /* Booked-at logo wall */
  .logo-wall {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 18px;
    margin-top: 24px;
  }
  .logo-tile {
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: 14px;
    height: 108px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 18px 24px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  }
  .logo-tile img { max-height: 54px !important; max-width: 180px !important; width: auto !important; height: auto !important; object-fit: contain; }
  .title-mark {
    width: 96px; height: 96px;
    border-radius: 20px;
    display: inline-block;
    margin-bottom: 28px;
    background-image: url('/root/Sonny/decks/assets/rc_logo.png');
    background-size: contain;
    background-repeat: no-repeat;
  }

  /* Authority grid */
  .auth-grid {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 14px; margin-top: 18px;
  }
  .auth-card {
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 16px 18px;
    background: #ffffff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    display: flex; flex-direction: column; gap: 4px;
  }
  .auth-card .logo {
    height: 28px; display: flex; align-items: center;
    margin-bottom: 6px;
  }
  .auth-card .logo img { height: 28px; width: auto; max-width: 120px; object-fit: contain; }
  .auth-card .logo .name { font-size: 16px; font-weight: 700; color: var(--fg); letter-spacing: -0.01em; }
  .auth-card .metric { font-size: 22px; font-weight: 800; color: var(--brand-2); }
  .auth-card .meta { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.12em; font-weight: 600; }
  .auth-card .desc { font-size: 12px; color: var(--fg-soft); margin-top: 4px; line-height: 1.4; }

  /* CTA button */
  .cta-btn {
    display: inline-block;
    padding: 14px 28px;
    background: linear-gradient(135deg, var(--brand-1), var(--brand-2), var(--brand-3));
    color: white !important;
    font-weight: 700;
    border-radius: 10px;
    font-size: 18px;
    letter-spacing: 0.02em;
    margin-top: 18px;
    text-decoration: none;
    box-shadow: 0 8px 24px rgba(253,82,53,0.25);
  }
---

<!-- _class: title -->

<!-- Slide 1: Title -->

<div class="blob blob-1"></div>
<div class="blob blob-2"></div>

{{TITLE_MARK_BLOCK}}

<div class="label" style="margin-bottom: 14px;">RevCentric × {{COMPANY_NAME}}</div>

# Pipeline you can <span class="grad">measure</span>.
# Built for <span class="grad">{{COMPANY_NAME}}</span>.

<div class="footer"><span>RevCentric</span><span>{{SENDER_EMAIL}}</span></div>

---

<!-- Slide 2: The Shift -->

<div class="grid"></div>

<div class="label">01 · The shift</div>

# {{SHIFT_HEADLINE}}<br>**{{SHIFT_PUNCHLINE}}**

<p style="font-size: 19px; max-width: 880px; line-height: 1.7;">{{SHIFT_BODY}}</p>

<div class="row" style="margin-top: 18px;">
  <div class="col">
    <div class="stat-num">{{SHIFT_STAT1_NUM}}</div>
    <h3>{{SHIFT_STAT1_HEAD}}</h3>
    <p>{{SHIFT_STAT1_BODY}}</p>
  </div>
  <div class="col">
    <div class="stat-num">{{SHIFT_STAT2_NUM}}</div>
    <h3>{{SHIFT_STAT2_HEAD}}</h3>
    <p>{{SHIFT_STAT2_BODY}}</p>
  </div>
  <div class="col">
    <div class="stat-num">{{SHIFT_STAT3_NUM}}</div>
    <h3>{{SHIFT_STAT3_HEAD}}</h3>
    <p>{{SHIFT_STAT3_BODY}}</p>
  </div>
</div>

<p style="margin-top: 18px; color: var(--muted); font-size: 16px; line-height: 1.7;">{{SHIFT_CLOSE}}</p>

---

<!-- Slide 4: Competitive Frame -->

<div class="label">02 · The category around {{COMPANY_NAME}}</div>

# {{COMPETE_HEAD1}}<br>**{{COMPETE_HEAD2}}**

<p style="font-size: 19px; max-width: 920px; line-height: 1.7;">{{COMPETE_INTRO}}</p>

<div class="vs-row">
  <div class="vs-col loser">
    <h4>{{COMPETITOR_NAME}}</h4>
    <p style="font-weight: 600; color: var(--fg);">{{COMPETITOR_TAGLINE}}</p>
    <p>{{COMPETITOR_LINE1}}</p>
    <p>{{COMPETITOR_LINE2}}</p>
    <p>{{COMPETITOR_LINE3}}</p>
  </div>
  <div class="vs-col winner">
    <h4>{{COMPANY_NAME}} + RevCentric</h4>
    <p style="font-weight: 600; color: var(--fg);">{{COMPANY_TAGLINE}}</p>
    <p>{{COMPANY_LINE1}}</p>
    <p>{{COMPANY_LINE2}}</p>
    <p>{{COMPANY_LINE3}}</p>
  </div>
</div>

---

<!-- Slide 5: The Promised Land -->

<div class="blob blob-1" style="top: auto; bottom: -200px; right: -150px;"></div>

<div class="label">03 · The outcome we own</div>

# Every {{THEIR_TARGET_TITLE}}.
# **On your calendar.**

<p style="font-size: 19px; max-width: 880px; line-height: 1.7;">What it looks like once outbound is running for {{COMPANY_NAME}}.<br>Three things change first.</p>

<div class="row" style="margin-top: 18px;">
  <div class="col">
    <div class="stat-word">Forecastable</div>
    <h3>Pipeline</h3>
    <p>Coverage you can model.</p>
    <p>Numbers the board respects.</p>
  </div>
  <div class="col">
    <div class="stat-word">Predictable</div>
    <h3>Volume</h3>
    <p>Conversations every week.</p>
    <p>Not feast or famine.</p>
  </div>
  <div class="col">
    <div class="stat-word">Closer-grade</div>
    <h3>Focus</h3>
    <p>Your team stays in deals.</p>
    <p>We handle the front end.</p>
  </div>
</div>

<p style="margin-top: 22px; color: var(--muted); font-size: 17px; line-height: 1.6; max-width: 880px;">No more guessing what next quarter looks like.<br>You see the supply of conversations before it hits the calendar.</p>

---

<!-- Slide 3: Founder-Led Content -->

<div class="label">04 · The 2026 GTM shift</div>

# Founder-led content moves the deal.
# **Outbound and inbound. Both.**

<p style="font-size: 19px; max-width: 920px; line-height: 1.7;">In 2026, the operators winning vertical B2B markets aren't just running ads.<br>They're building <strong>personal brand</strong> as the wedge. Outbound is the multiplier on top of it.</p>

<div class="row" style="margin-top: 14px; gap: 14px;">
  <div class="col" style="text-align: center; padding: 16px 14px;">
    <div class="avatar-wrap"><img src="/root/Sonny/decks/assets/atharva_padhye_sq.jpg"/></div>
    <h3 style="text-align: center;">Atharva Padhye · GetCrux</h3>
    <p style="font-weight: 600; color: var(--fg); text-align: center; font-size: 14px;">Builds the category</p>
    <p style="text-align: center; font-size: 13px;">YC W23.<br>1.5K+ brands tracked.<br><strong>21K followers</strong></p>
  </div>
  <div class="col" style="text-align: center; padding: 16px 14px;">
    <div class="avatar-wrap"><img src="/root/Sonny/decks/assets/paul_vanmetre_sq.jpg"/></div>
    <h3 style="text-align: center;">Paul Van Metre · ProShop ERP</h3>
    <p style="font-weight: 600; color: var(--fg); text-align: center; font-size: 14px;">Chief Industry Evangelist</p>
    <p style="text-align: center; font-size: 13px;">Hosts 2 podcasts.<br>Title exists for content.<br><strong>21K followers</strong></p>
  </div>
  <div class="col" style="text-align: center; padding: 16px 14px;">
    <div class="avatar-wrap"><img src="/root/Sonny/decks/assets/adam_robinson_sq.jpg"/></div>
    <h3 style="text-align: center;">Adam Robinson · RB2B</h3>
    <p style="font-weight: 600; color: var(--fg); text-align: center; font-size: 14px;">Builds in public</p>
    <p style="text-align: center; font-size: 13px;">$0 → $20M ARR.<br>Posts revenue daily.<br><strong>153K followers</strong></p>
  </div>
  <div class="col" style="text-align: center; padding: 16px 14px;">
    <div class="avatar-wrap"><img src="/root/Sonny/decks/assets/hunter_deskin_sq.jpg"/></div>
    <h3 style="text-align: center;">Hunter Deskin · RevCentric</h3>
    <p style="font-weight: 600; color: var(--fg); text-align: center; font-size: 14px;">Operator-founder</p>
    <p style="text-align: center; font-size: 13px;">Posts what books.<br>Books from the post.<br><strong>16K followers</strong></p>
  </div>
</div>

<p style="margin-top: 14px; font-size: 15px; line-height: 1.6; color: var(--fg);"><strong>Buyers are 5x more likely to engage</strong> with a seller they're already connected to or have seen content from.<br><em style="color: var(--muted);">- LinkedIn State of Sales 2024.</em></p>

---

<!-- Slide 6: What we'd do -->

<div class="label">05 · What we'd do for {{COMPANY_NAME}}</div>

# Done-for-you outbound.
# **Performance-based.**

<p style="font-size: 19px; max-width: 880px; line-height: 1.7;">Cold call · email · LinkedIn. Fully managed.<br>We own the <strong>tech</strong>, <strong>data</strong>, <strong>lists</strong>, and <strong>process</strong>.<br>You receive booked calls with {{THEIR_TARGET_TITLE}}.</p>

<div class="row">
  <div class="col">
    <h3>What you get</h3>
    <p>Vetted SDRs (1+ yr outbound)</p>
    <p>Tech stack we own end-to-end</p>
    <p>List building + enrichment</p>
    <p>Weekly reporting</p>
  </div>
  <div class="col">
    <h3>Engagement</h3>
    <p>Outcome-based.</p>
    <p>You don't pay for activity. You pay for results.</p>
    <p>Setup & management is recoverable if results don't land. <em>In writing.</em></p>
  </div>
  <div class="col">
    <h3>Why it fits {{COMPANY_NAME}}</h3>
    <p>{{WHY_OUTBOUND_FITS}}</p>
  </div>
</div>

---

<!-- Slide 7: Authority / Case Studies -->

<div class="label">06 · Track record</div>

# **$25M+** in pipeline.
# **36 months. Phone-led.**

<p style="font-size: 19px; max-width: 880px; line-height: 1.7;">Across companies that look like {{COMPANY_NAME}} on the org chart.<br>Operator-founders, vertical markets, phone-first ICPs.</p>

<div class="auth-grid">
  <div class="auth-card">
    <div class="logo"><img src="/root/Sonny/decks/assets/rc_whoisxml.svg"/></div>
    <div class="metric">$5M Pipeline</div>
    <div class="meta">B2B SaaS · Cybersecurity</div>
    <div class="desc">WhoIsXML & Attaxion · 150 booked meetings, 100+ demos · 9 months</div>
  </div>
  <div class="auth-card">
    <div class="logo"><img src="/root/Sonny/decks/assets/rc_micro-estimating.png"/></div>
    <div class="metric">$2M Pipeline</div>
    <div class="meta">B2B SaaS</div>
    <div class="desc">Micro Estimating · 64 demos, 22 disco, 58 proposals · 4 months</div>
  </div>
  <div class="auth-card">
    <div class="logo"><img src="/root/Sonny/decks/assets/rc_startproto.svg"/></div>
    <div class="metric">$1M+ Pipeline</div>
    <div class="meta">B2B SaaS · Machine Shops</div>
    <div class="desc">StartProto · 10–12 mtgs/mo at $12K–$25K ACV · 21 weeks</div>
  </div>
  <div class="auth-card">
    <div class="logo"><img src="/root/Sonny/decks/assets/rc_paperless-parts.svg"/></div>
    <div class="metric">$500K+ Pipeline</div>
    <div class="meta">B2B SaaS · MFG</div>
    <div class="desc">Paperless Parts · 50+ enterprise meetings · 16 weeks</div>
  </div>
  <div class="auth-card">
    <div class="logo"><img src="/root/Sonny/decks/assets/getcrux_g.png"/></div>
    <div class="metric">$250K+ ARR</div>
    <div class="meta">B2B SaaS · Marketing Analytics</div>
    <div class="desc">GetCrux · 40+ meetings in 60 days · HubSpot, Truist, Robinhood · 6 mo · Phone-led</div>
  </div>
  <div class="auth-card">
    <div class="logo"><img src="/root/Sonny/decks/assets/rc_bandalier.svg"/></div>
    <div class="metric">$280K Revenue</div>
    <div class="meta">B2B Services · VC-backed</div>
    <div class="desc">Bandalier · 30 opportunities, 2 closed deals · 6 months</div>
  </div>
</div>


---

<!-- Slide 8b: Booked At Wall -->

<div class="label">07 · Rooms we got into</div>

# The names most teams chase for years.
# **Our SDRs got the meeting.**

<p style="font-size: 19px; max-width: 880px; line-height: 1.7;">A sample of the buyers our SDRs put on our clients' calendars.<br>Cold. Outbound. No warm intros.</p>

<div class="logo-wall">
  <div class="logo-tile"><img src="/root/Sonny/decks/assets/bookedat_disney.svg"/></div>
  <div class="logo-tile"><img src="/root/Sonny/decks/assets/bookedat_wellsfargo.svg"/></div>
  <div class="logo-tile"><img src="/root/Sonny/decks/assets/bookedat_verizon.svg"/></div>
  <div class="logo-tile"><img src="/root/Sonny/decks/assets/bookedat_ebay.svg"/></div>
  <div class="logo-tile"><img src="/root/Sonny/decks/assets/bookedat_hubspot.svg"/></div>
  <div class="logo-tile"><img src="/root/Sonny/decks/assets/bookedat_truist.svg"/></div>
  <div class="logo-tile"><img src="/root/Sonny/decks/assets/bookedat_robinhood.svg"/></div>
  <div class="logo-tile"><img src="/root/Sonny/decks/assets/bookedat_tripadvisor.svg"/></div>
</div>

---

<!-- Slide 8: Two Paths -->

<div class="grid"></div>

<div class="label">08 · How we'd plug in</div>

# Two engagements.
# **Both performance-tied.**

<p style="font-size: 19px; max-width: 880px; line-height: 1.7;">Two ways we plug in for {{COMPANY_NAME}}.<br>Both end the same way: you only pay for outcomes.</p>

<p style="font-size: 16px; color: var(--muted); margin-bottom: 8px;"><strong>Aligned on outcomes.</strong> The bulk of what you pay is tied to performance. If results don't show up, neither does the invoice that depends on them.</p>

<div class="row">
  <div class="col">
    <h3>Accelerator · 6 months</h3>
    <p style="font-size: 17px; font-weight: 600; color: var(--fg);">If you're already running outbound</p>
    <p>We come in alongside.<br>Different list. Different angle.<br>A clean benchmark vs internal.</p>
  </div>
  <div class="col">
    <h3>Enterprise · 12 months</h3>
    <p style="font-size: 17px; font-weight: 600; color: var(--fg);">If outbound isn't built (or isn't working)</p>
    <p>ICP conversations at scale.<br>We find what books reliably for {{COMPANY_NAME}}.<br>Then scale it. Or kill it.</p>
  </div>
</div>

---

<!-- Slide 9: The Ask -->

<div class="blob blob-1" style="top: -200px; right: -200px; width: 600px; height: 600px;"></div>
<div class="blob blob-2" style="bottom: -250px; left: -200px; width: 500px; height: 500px;"></div>

<div class="label" style="position: relative;">09 · The ask</div>

# {{ASK_HEAD1}}<br>**{{ASK_HEAD2}}**

<p style="font-size: 19px; max-width: 880px; margin-top: 14px; line-height: 1.7;">{{ASK_INTRO}}</p>

<div class="row" style="margin-top: 18px;">
  <div class="col">
    <h3>Pricing</h3>
    <p style="font-weight: 600; color: var(--fg);">Tied to outcomes.</p>
    <p>You pay on results, not on hours logged.</p>
  </div>
  <div class="col">
    <h3>Risk</h3>
    <p style="font-weight: 600; color: var(--fg);">Carried by us, not you.</p>
    <p>Setup & management is recoverable if performance doesn't land.</p>
  </div>
  <div class="col">
    <h3>Documented</h3>
    <p style="font-weight: 600; color: var(--fg);">Terms in writing.</p>
    <p>What we owe you and what triggers it. Black and white.</p>
  </div>
</div>

<a href="{{BOOKING_LINK}}" class="cta-btn">{{CTA_LABEL}} →</a>

<div class="footer"><span>RevCentric</span><span>{{SENDER_EMAIL}}</span></div>
