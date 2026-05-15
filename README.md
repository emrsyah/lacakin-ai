# Lacakin — Multi-Agent Stolen-Motorcycle Tracker

<img width="1672" height="941" alt="ChatGPT Image 15 Mei 2026, 20 32 33" src="https://github.com/user-attachments/assets/6e242949-5ef2-4edc-86ff-c7232cd6d559" />


> Built for **Agenthon 2026** (12-hour hackathon) on top of the **OpenClaw**
> multi-agent orchestration framework.

Indonesia loses thousands of motorcycles to theft every year. Reporting one to
the police involves manual paperwork, and victims have no real-time visibility
into whether their motor has been spotted anywhere. **Lacakin** ("lacak" =
"track" in Indonesian) closes that gap: a Telegram-native swarm of AI agents
that watches Bandung public CCTV, scans Facebook listings, monitors spare-parts
forums, and drafts an official police report — all from a single user message.

---

## Table of Contents

1. [Features](#features)
2. [Architecture at a Glance](#architecture-at-a-glance)
3. [The Seven Agents](#the-seven-agents)
4. [Agent Lifecycle (Heartbeat Tick)](#agent-lifecycle-heartbeat-tick)
5. [Two-Stage Vision Pipeline](#two-stage-vision-pipeline)
6. [Agent-to-Agent (A2A) Protocol](#agent-to-agent-a2a-protocol)
7. [MCP Server Inventory](#mcp-server-inventory)
8. [External Skills](#external-skills)
9. [Workspace & Filesystem Layout](#workspace--filesystem-layout)
10. [Repository Layout](#repository-layout)
11. [How to Reproduce](#how-to-reproduce)
12. [Tests](#tests)
13. [Team Split (Hackathon)](#team-split-hackathon)

---

## Features

| Capability | Detail |
|---|---|
| **Case intake** | User describes the stolen motor (type, colour, plate, last-seen location/time) in plain Bahasa Indonesia via Telegram to `@lacakin` |
| **CCTV surveillance** | Headless browser scrapes Bandung public CCTV from `pelindung.bandung.go.id`; Jina CLIP v2 text↔image scores each snapshot against the case description |
| **Marketplace scan** | Facebook Marketplace Bandung searched for fresh listings matching make/model/colour; Jina image↔image scores against the victim's reference photo |
| **Parts-market watch** | Detects component listings matching the stolen bike's make/year in known parts forums |
| **Social-media monitor** | Facebook top-search keyword scan (no login, no interaction) for jualan posts that aren't on Marketplace |
| **Police report draft** | Structured `laporan` rendered from a template by the Polisi agent, ready to submit |
| **PDF synthesis** | Report agent collates all findings on its own cron-like heartbeat, renders a styled PDF via reportlab, and posts it to the group as a Telegram document |
| **Live link previews** | Any browser-using agent can call `send_link_preview(url, caption?)` to navigate to a URL headlessly, screenshot it, and post the image to the group with one tool call — used to share "look at this page" without writing a finding row |
| **Agent-to-agent messaging** | Workers tip each other (e.g. CCTV → sosmed with a fresh location) via a SQLite-backed A2A inbox with TTL + cycle protection |
| **Demo mode** | Fixture-cached vision responses + staged frames guarantee a full detection flow at T+35s in demos |

---

## Architecture at a Glance

```
                      User in Telegram group
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    OpenClaw Gateway                          │
│  ─ 7 bots, one per agent (each with its own BotFather token) │
│  ─ Each agent appears as an independent group participant    │
│  ─ Gateway handles: identity, broadcast, mention routing,    │
│    heartbeat scheduling, agentToAgent tool exposure          │
└─────────────┬────────────────────────────────────────────────┘
              │
              │  spawn / heartbeat / broadcast / mention-route
              ▼
┌──────────────────────────────────────────────────────────────┐
│                        Agent Swarm                           │
│                                                              │
│      orchestrator (Lacakin)  ◄── intake, fan-out, dispatch   │
│         ▲                                                    │
│  ┌──────┴────────────────────────────────────────────┐       │
│  │           workers (run on their own ticks)        │       │
│  │   cctv          marketplace      parts            │       │
│  │   sosmed        report (cron)                     │       │
│  └───────────────────────────────────────────────────┘       │
│                                                              │
│      polisi  ◄── invoked on demand (no heartbeat)            │
└─────────────┬────────────────────────────────────────────────┘
              │
              │  MCP stdio (per-agent allowlist)
              ▼
┌──────────────────────────────────────────────────────────────┐
│                       MCP Servers                            │
│                                                              │
│  browser-mcp   Playwright Chromium: CCTV snapshots + FB scan │
│  vision-mcp    Jina CLIP v2 (image↔image, text↔image)        │
│                + Gemini Flash Lite plate OCR                 │
│                + Gemini Flash structured reasoning           │
│  db-mcp        SQLite findings + case-context store          │
│  a2a-mcp       Agent inbox (SQLite + TTL + cycle check)      │
│  polisi-mcp    Police report template renderer               │
│  ops-mcp       Telegram send (photo/document/status)         │
│                + PDF rendering (reportlab + fallback)        │
└──────────────────────────────────────────────────────────────┘
```

Three pieces deserve attention:

- **One bot per agent.** The gateway binds each agent to its own Telegram bot,
  so the group sees seven distinct participants (`@mata_bandung_bot`,
  `@pasar_bot`, etc.) instead of a single super-bot. This is what makes the
  Telegram-side experience feel like a coordinated team rather than a monolith.
- **Workers are sandboxed; orchestrator and report are not.** Workers run with
  `sandbox: { mode: "all", scope: "agent" }` and have `browser` access. The
  orchestrator and polisi/report agents run unsandboxed but with much tighter
  tool allowlists (`read`/`write` only — all side-effects flow through MCPs).
- **MCPs are the only side-effect channel.** Workers never call Telegram or the
  database directly; everything routes through MCP servers so the agents stay
  prompt-driven and replaceable.

---

## The Seven Agents

Each row below maps to one entry in `openclaw/agents.json5` and one workspace
under `~/lacakin/workspace-<id>/`.

| Agent | Telegram persona | Model | Heartbeat | Tools allowed | MCP allowlist | Role |
|---|---|---|---|---|---|---|
| `orchestrator` | Lacakin 🛵 (calm investigator) | gemini-2.5-flash | none (event-driven) | read, write, edit, sessions_* | db, a2a, ops | Intake, case context, fan-out to workers |
| `cctv` | Mata Bandung 👁️ (lookout) | gemini-2.5-flash-lite | 30s demo / 5m prod | read, write, browser | browser, vision, db, a2a, ops | Snapshot pelindung CCTV, score vs case text |
| `marketplace` | Pemantau Pasar 🛒 (market trader) | gemini-2.5-flash-lite | 45s / 10m | read, write, browser | browser, vision, db, a2a, ops | Watch Facebook Marketplace Bandung listings |
| `parts` | Pemburu Suku Cadang 🔧 (parts specialist) | gemini-2.5-flash-lite | 60s / 15m | read, write, browser | browser, vision, db, a2a, ops | Hunt part-outs and stripped-unit listings |
| `sosmed` | Pengintai Sosmed 📱 (social stalker) | gemini-2.5-flash-lite | 45s / 10m | read, write, browser | browser, vision, db, a2a, ops | Facebook top-search public posts (no login) |
| `polisi` | Polisi-AI 👮 (birokrat) | gemini-2.5-flash-lite | none (on demand) | read, write | db, polisi, ops | Draft formal police reports |
| `report` | Pencatat Laporan 📋 (neutral chronicler) | gemini-2.5-flash | 90s / 30m | read, write | db, a2a, ops | Cluster findings, render PDF, send to group |

Each worker's behaviour is split into two files copied into its workspace by
`scripts/setup_vps.sh`:

- `SOUL.md` — persona and tone (one-shot, never reloaded mid-run).
- `HEARTBEAT.md` — the per-tick procedure (re-read every tick).

Both files reference shared docs that also live in the workspace:

- `LACAKIN_SKILLS.md` — cross-agent operational rules.
- `A2A_PROTOCOL.md` — inbox-first, cycle-safe messaging protocol.
- `BROWSER_SKILL.md` — when to use the `agent-browser` CLI vs `browser-mcp`.
- `REPORT_PDF_SKILL.md` *(report agent only)* — how the PDF tool wraps the
  anthropics `pdf` skill.

---

## Agent Lifecycle (Heartbeat Tick)

Every worker follows the same nine-step recipe (the exact step list is in each
`heartbeat_*.md`). This is the contract that makes the swarm feel coherent:

```
┌─ tick fires ──────────────────────────────────────────────────┐
│ 1. Read SKILLS + BROWSER_SKILL                                │
│ 2. a2a_inbox(to_agent=self) ─── apply pivots from peers       │
│ 3. Re-read shared/CONTEXT.md                                  │
│    └─ if Status: CLOSED → exit                                │
│ 4. Re-read findings.md (dedup against last 5 minutes)         │
│ 5. Do the agent-specific work:                                │
│    ─ CCTV       : screenshot 3 cameras                        │
│    ─ marketplace: FB Marketplace search (≤5 candidates)       │
│    ─ parts      : parts-forum search                          │
│    ─ sosmed     : FB top-search screenshots (≤3 queries)      │
│    ─ report     : list_findings → cluster → render PDF        │
│ 6. Vision pipeline (two stages — see below)                   │
│ 7. On HIGH match: write_finding + send_telegram_photo         │
│    + a2a_send to suggested route_to agents                    │
│ 8. post_heartbeat_status(visible=false)                       │
│ 9. a2a_tick_done(to_agent=self)  ─── STOP, no loop            │
└───────────────────────────────────────────────────────────────┘
```

**Hard rules that apply to every worker:**

- One tick = bounded work (max 3 cameras, 5 listings, 3 queries). The agent
  never loops within a tick — the next tick fires later if there's more to do.
- Visible Telegram posts are rationed: visible on case start, on A2A task
  received, on `HIGH` evidence, and every 10th otherwise-quiet sweep.
- `a2a_tick_done` is mandatory — the gateway uses it to know the worker is
  idle again. Skipping it means `skipWhenBusy:true` will swallow the next tick.

---

## Two-Stage Vision Pipeline

The vision MCP exposes **two** cheap pre-filters and one expensive Sonnet
reasoner. Agents pick the right Stage-1 based on what they have:

```
                              Stage 1 (Jina CLIP v2)
                              ─────────────────────
   ┌─────────────────────────┐                      ┌─────────────────────────┐
   │ Have a reference photo  │                      │ Only have text (query   │
   │ (marketplace, parts)    │                      │ or case description)    │
   │                         │                      │ (cctv, sosmed)          │
   │  match_image            │                      │  match_text_image       │
   │  cosine (image, image)  │                      │  cosine (text,  image)  │
   │  thresholds:            │                      │  thresholds:            │
   │   <0.55 drop            │                      │   <0.18 drop            │
   │   0.55–0.70 log only    │                      │   0.18–0.25 log only    │
   │   ≥0.70 ESCALATE        │                      │   ≥0.25 ESCALATE        │
   └───────────────┬─────────┘                      └────────────┬────────────┘
                   │                                             │
                   └──────────────────┬──────────────────────────┘
                                      ▼
                          Stage 2 (Gemini 2.5 Flash)
                          ───────────────────────────
                          reason_about_candidate(image, context_md, source_type)

                          → structured JSON:
                              match_confidence  (0..1)
                              matches[]         (e.g. "tangki merah", "stiker X")
                              mismatches[]
                              suspicious_signals[]
                              narrative         (1-3 sentences)
                              route_to[]        (next agent + reason)
                          + (optional) read_plate via Gemini Flash Lite vision
```

Text↔image cosines sit at a much lower absolute range than image↔image — 0.25
text-to-image is "this image is clearly about that text," roughly equivalent in
selectivity to 0.70 image-to-image. The two threshold tables in
`vision_mcp/server.py` reflect this and **must not** be merged into one.

Stage 1 costs ~$0.001/call via Jina. Stage 2 (Sonnet) is invoked only on
candidates that pass Stage 1. Stage-2 outputs include a `route_to[]` array,
which directly drives the A2A `a2a_send` calls — Sonnet decides who to ping
next, the agent just executes.

For demo runs, Stage 2 is fixture-cached: `register_demo_fixtures.py`
pre-registers SHA-256-keyed responses so staged demo frames deterministically
produce a high-confidence narrative without live API calls.

---

## Agent-to-Agent (A2A) Protocol

The A2A MCP is a tiny SQLite-backed inbox. Its public surface is four tools:

| Tool | Purpose |
|---|---|
| `a2a_send(case_id, from_agent, to_agent, reason, payload, ttl_ticks, chain_id?)` | Drop a message into another agent's inbox. Allocates a fresh `chain_id` if none given. |
| `a2a_inbox(to_agent)` | List unconsumed messages for an agent. Auto-decrements TTL and filters expired rows. |
| `a2a_consume(message_ids[])` | Mark messages as processed. |
| `a2a_tick_done(to_agent)` | Signal "I'm done with this tick" (frees `skipWhenBusy` lock). |

**Three properties keep this from blowing up:**

1. **TTL (`ttl_ticks`).** Every message carries a tick counter; reaching zero
   makes the message disappear. Prevents stale pivots from haunting later
   ticks.
2. **`chain_id` cycle break.** Each message inherits the sender's
   `chain_id`; the inbox rejects sends where the same `chain_id` has visited
   the recipient before in this case. Cuts A → B → A → B oscillation dead.
3. **Scoped by `case_id`.** Multiple investigations can run in parallel; an
   A2A from case X never leaks into case Y's inbox.

**Swarm awakening.** On case intake, the orchestrator sends four sequential
`reason="initial_sweep"` pings (ttl=1) to `cctv`, `marketplace`, `sosmed`,
`parts`. Each worker's next heartbeat sees the message, posts a visible
"saya mulai…" line in the group, and starts work — giving the impression of a
team springing into action within seconds. The single `ttl=1` ensures the
opening salvo doesn't echo into later ticks.

**Route-to driven escalation.** Sonnet's Stage-2 output ends with a
`route_to: [{agent, reason}, ...]` array. The agent that ran the inference
turns each entry into an `a2a_send`, optionally @-mentioning the target bot
in the same Telegram post. This is how a CCTV hit ends up triggering both
the sosmed agent (look for fresh listings nearby) and the marketplace agent
(check for the unit being flipped).

---

## MCP Server Inventory

All MCPs are FastMCP servers launched by the OpenClaw gateway as stdio
subprocesses (see `openclaw/agents.json5:mcp.servers`). The current tool
surface:

### `browser-mcp` — `mcp/browser_mcp/server.py`
- `cctv_snapshot(camera_id)` → `{path, ts, camera_id, area}` — single still
  from a pelindung.bandung.go.id camera. URLs in `cameras.json`.
- `list_cameras(near_lat?, near_lon?, radius_km?)` — filter the 10 known
  Bandung cameras by distance.
- `marketplace_search(platform, query, limit?)` — Facebook / Tokopedia / OLX
  card scraping. Default platform: `facebook`.
- `marketplace_get_listing(url)` — listing detail page + downloads up to 5
  images to `shared/photos/listings/<slug>/`.

### `vision-mcp` — `mcp/vision_mcp/server.py`
- `match_image(reference_path, candidate_path)` — Jina CLIP v2 image↔image
  cosine, 0..1.
- `match_text_image(text, image_path)` — Jina CLIP v2 text↔image cosine; used
  by CCTV (case description) and sosmed (FB query).
- `read_plate(image_path)` — Indonesian plate OCR via the configured vision model (default `gemini-2.5-flash-lite`).
- `reason_about_candidate(image_path, context_md, source_type)` — Stage-2
  structured JSON via the configured vision model (default `gemini-2.5-flash`), with the fixture cache layer.

### `db-mcp` — `mcp/db_mcp/server.py`
- `write_context(case_id, context_md)` / `get_context(case_id)` /
  `close_case(case_id)` — case lifecycle.
- `write_finding(case_id, agent_id, severity, note, score?, image_path?, link?)`
  — append-only evidence log.
- `list_findings(case_id, since_iso?, severity?)` / `undelivered(case_id)` /
  `mark_delivered(finding_ids[])` — query + delivery bookkeeping for the
  report agent.

### `a2a-mcp` — `mcp/a2a_mcp/server.py`
- `a2a_send`, `a2a_inbox`, `a2a_consume`, `a2a_tick_done` (see protocol
  section above). Internal helpers `cycle_check`, `ttl_decrement` are private.

### `polisi-mcp` — `mcp/polisi_mcp/server.py`
- `draft_laporan(case_id, ...)` — fills the official `laporan kehilangan`
  template with case data; returns a plain-text body suitable for paste-into
  a real police desk.

### `ops-mcp` — `mcp/ops_mcp/server.py`
- `render_report_pdf(case_id, markdown, title?)` — hand-rolled PDF (latin-1,
  used as fallback only).
- `render_report_pdf_skill(case_id, markdown, title?)` — UTF-8-safe styled
  PDF via reportlab/Platypus, following the recipe in the anthropics `pdf`
  skill. **Preferred renderer.** Returns `{ pdf_path, markdown_path, bytes,
  renderer }`.
- `send_telegram_document(agent_id, file_path, caption?, chat_id?)` — send
  arbitrary file via the agent's bot token.
- `send_telegram_photo(agent_id, image_path, caption?, chat_id?)` — send a
  finding image.
- `send_link_preview(agent_id, url, caption?, viewport?, wait_ms?, chat_id?)`
  — one-shot **share a live URL with the group**: navigates headless
  Chromium → viewport screenshot → posts to Telegram with the URL
  auto-appended to the caption. Used for "look at this page" shares without
  writing a finding row. Returns `{ ok, screenshot_path, url, telegram }`.
- `post_heartbeat_status(agent_id, status, case_id?, chat_id?, visible?)` —
  record an internal status line; optionally also post it to the group.

---

## External Skills

Lacakin uses two upstream skills installed via `npx skills add`:

| Skill | Source | Used by | Purpose |
|---|---|---|---|
| `agent-browser` | `vercel-labs/agent-browser` | cctv, marketplace, parts, sosmed | Fallback browser driver when `browser-mcp` is blocked (login wall, CAPTCHA) or when a full-page screenshot of an arbitrary URL is needed. CLI: `npx agent-browser screenshot --url <u> --out <p>`. |
| `pdf` | `anthropics/skills` | report (via ops-mcp wrapper) | reportlab/pypdf recipe for markdown→styled-PDF. Not invoked directly by the agent — wrapped behind `render_report_pdf_skill` in ops-mcp so the report agent's tool allowlist stays at `read,write`. |

Both are installed by `scripts/setup_vps.sh` and tracked in `skills-lock.json`.

---

## Workspace & Filesystem Layout

OpenClaw gives each agent a private working directory. `setup_vps.sh`
provisions them and symlinks a shared dir:

```
~/lacakin/
├── shared/                         (one canonical copy)
│   ├── CONTEXT.md                  ← active case (orchestrator writes)
│   ├── findings/                   ← findings stream (one file per agent)
│   ├── reports/                    ← rendered PDFs + REPORT.md latest copy
│   ├── photos/                     ← CCTV stills + downloaded listing images
│   │   ├── <camera_id>/<ts>.jpg
│   │   ├── listings/<slug>/N.jpg
│   │   └── sosmed/<ts>_<slug>.jpg
│   └── status/                     ← post_heartbeat_status archive
├── lacakin.db                      ← SQLite (findings + A2A + cases)
└── workspace-<agent>/
    ├── shared      → symlink to ~/lacakin/shared
    ├── SOUL.md                     (persona)
    ├── SYSTEM.md or HEARTBEAT.md   (main prompt)
    ├── LACAKIN_SKILLS.md
    ├── A2A_PROTOCOL.md
    ├── BROWSER_SKILL.md            (browser-using agents only)
    ├── REPORT_PDF_SKILL.md         (report agent only)
    ├── cameras.json                (cctv agent only)
    └── findings.md                 (per-agent journal)
```

Critically, the agent prompts are deliberately **referenced from the
workspace, not embedded in `agents.json5`** — that way the prompts can be
rev'd by re-running `setup_vps.sh` without restarting the gateway or
re-deploying config.

---

## Repository Layout

```
lacakin-ai/
├── openclaw/
│   ├── agents.json5             # Gateway config: 7 bots, MCPs, bindings
│   └── prompts/
│       ├── A2A_PROTOCOL.md      # Shared inbox-first protocol
│       ├── LACAKIN_SKILLS.md    # Cross-agent operational rules
│       ├── BROWSER_SKILL.md     # When to use agent-browser CLI
│       ├── REPORT_PDF_SKILL.md  # PDF skill wrapper notes (report agent)
│       ├── main_system.md       # Orchestrator system prompt
│       ├── polisi_system.md     # Polisi system prompt
│       ├── report_system.md     # Report agent system prompt
│       ├── heartbeat_cctv.md    # Per-tick procedure (cctv)
│       ├── heartbeat_marketplace.md
│       ├── heartbeat_parts.md
│       ├── heartbeat_sosmed.md
│       └── souls/               # Persona / tone (one per agent)
├── mcp/
│   ├── browser_mcp/             # Playwright: cctv + marketplace
│   │   ├── server.py
│   │   └── cameras.json         # 10 Bandung cameras (pelindung.bandung.go.id)
│   ├── vision_mcp/              # Jina CLIP + Claude vision
│   │   ├── server.py            # match_image, match_text_image, read_plate, reason_about_candidate
│   │   ├── sonnet_reason.py     # Stage-2 structured vision reasoning
│   │   ├── fixture_cache.py     # SHA-256-keyed demo fixture store
│   │   └── fixtures/            # Pre-cached Sonnet responses for staged frames
│   ├── db_mcp/                  # Findings + case context (SQLite)
│   ├── a2a_mcp/                 # Agent inbox (SQLite + TTL + cycle check)
│   ├── polisi_mcp/              # Police report template renderer
│   └── ops_mcp/                 # Telegram + PDF + status
├── demo_assets/
│   ├── reference/               # honda-beat-reference.jpg
│   ├── cctv_clips/              # Staged frames + static HTML for demo CCTV
│   └── fake_listings/           # Staged marketplace cards
├── scripts/
│   ├── setup_vps.sh             # Full VPS bootstrap (deps + skills + prompts)
│   ├── patch_openclaw.sh        # Idempotent re-apply of patches/prompts
│   ├── seed_demo.py             # Creates demo case + fake listing
│   ├── register_demo_fixtures.py # Pre-caches Sonnet responses for demo
│   └── smoke_e2e.py             # 4-check sanity script
├── tests/                       # pytest suite (no API calls needed for default markers)
├── .env.demo                    # Demo cadences (30s/45s/60s/45s/90s)
├── .env.prod                    # Prod cadences (5m/10m/15m/10m/30m)
├── skills-lock.json             # Pinned external skill versions
└── requirements.txt             # Python deps (incl. reportlab, playwright, openai)
```

---

## How to Reproduce

### Prerequisites

- Python 3.10–3.12 (3.13 works but a couple of deps lag behind)
- Node.js 18+ (for OpenClaw gateway and `npx skills`)
- A Linux VPS (tested on Ubuntu 22.04+)
- 7 Telegram bots created via [@BotFather](https://t.me/BotFather)
- API keys: `OPENAI_API_KEY` (any OpenAI-compatible provider works — set `OPENAI_BASE_URL` to e.g. `https://ai.sumopod.com/v1`), `JINA_API_KEY`

### 1. Clone and install

```bash
git clone https://github.com/<your-org>/lacakin-ai
cd lacakin-ai
bash scripts/setup_vps.sh        # installs system deps, venv, Chromium, both skills, distributes prompts
```

`setup_vps.sh` is idempotent — re-run it whenever you change a prompt file or
bump a skill.

### 2. Create Telegram bots

Create seven bots via BotFather (one per agent):

```
orchestrator, cctv, marketplace, parts, sosmed, polisi, report
```

For each: `/setprivacy → Disable` (otherwise the bot can't read group messages
it isn't @-mentioned in).

### 3. Configure environment

```bash
cp .env.demo .env
$EDITOR .env   # fill in OPENAI_API_KEY (+ OPENAI_BASE_URL), JINA_API_KEY, all 7 TELEGRAM_TOKEN_*,
               # LACAKIN_GROUP_ID, LACAKIN_SHARED, LACAKIN_DB
```

### 4. Place demo assets (optional, for the canned demo flow)

```
demo_assets/reference/honda-beat-reference.jpg   ← victim's reference photo
demo_assets/cctv_clips/staged-motor-frame.jpg    ← pre-staged CCTV frame
demo_assets/fake_listings/staged-motor-frame.jpg ← pre-staged listing card
```

### 5. Seed the demo case + fixtures

```bash
source .env.demo && source .env
python scripts/seed_demo.py                # writes CONTEXT.md + a fake listing
python scripts/register_demo_fixtures.py   # caches Sonnet vision responses
```

### 6. Validate and start

```bash
openclaw validate --config openclaw/agents.json5
openclaw start    --config openclaw/agents.json5
```

For production cadences: `source .env.prod` instead of `.env.demo` before
`openclaw start`.

Add all 7 bots to your Telegram group, then message:

```
@lacakin motor saya dicuri! Honda Beat merah, plat D 4821 ZX,
terakhir di Jl. Dago simpang pukul 22:30 semalam.
```

You should see the orchestrator confirm intake, then within ~30s see the four
worker bots each post their opening line as the `initial_sweep` A2A pings
land. The first `HIGH` finding triggers an image post to the group; the report
agent's next tick produces a PDF.

---

## Tests

```bash
pytest -v -m "not needs_api"   # default suite, no API keys needed
pytest -v                      # full suite, needs OPENAI_API_KEY + JINA_API_KEY
```

The `not needs_api` marker covers the A2A protocol, db schema, fixture cache
hit-rates, and ops-mcp's PDF byte-shape — i.e. all the orchestration plumbing
that should never depend on a live API.

---

## Team Split (Hackathon)

| Person | Owns |
|---|---|
| **A** | `openclaw/` — gateway config, prompts, Telegram binding, swarm awakening, demo flow |
| **B** | `mcp/` — six Python MCP servers (browser, vision, db, a2a, polisi, ops) |
| **C** | `scripts/`, report agent prompt, demo seed data, demo fixtures, recording |
