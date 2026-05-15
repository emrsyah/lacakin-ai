# Lacakin — Multi-Agent Stolen-Motorcycle Tracker

> Built for **Agenthon 2026** (12-hour hackathon) on top of the **OpenClaw** multi-agent orchestration framework.

Indonesia loses thousands of motorcycles to theft every year. Reporting one to the
police involves manual paperwork, and victims have no real-time visibility into
whether their motor has been spotted anywhere. **Lacakin** ("lacak" = track in Indonesian)
closes that gap: a Telegram-native swarm of AI agents that watches CCTV feeds,
scans marketplace listings, monitors spare-parts forums, and drafts an official
police report — all from a single user message.

---

## Features

| Capability | Detail |
|---|---|
| **Case intake** | User describes stolen motor (type, colour, plate, location, time) in plain Bahasa Indonesia via Telegram |
| **CCTV surveillance** | Headless browser scrapes live Bandung traffic camera feeds; Jina CLIP v2 matches candidate frames against the reference photo |
| **Marketplace scan** | Tokopedia + OLX searched for suspiciously cheap listings matching the motor model; vision reasoning flags oddities |
| **Parts-market watch** | Detects component listings that match the stolen bike's make/year in known parts forums |
| **Social-media monitor** | Twitter/X and Facebook keyword scan for plate sightings |
| **Police report draft** | Structured `laporan` rendered from a template, ready to submit to Saber Pungli / Bareskrim |
| **Periodic synthesis** | Report agent collates all findings on a cron-like heartbeat and posts a narrative summary to the group |
| **Agent-to-agent messaging** | Agents tip each other (e.g. CCTV pings marketplace with a location) via an SQLite-backed A2A inbox |
| **Demo mode** | Fixture-cached Sonnet responses + staged frames guarantee a full detection flow at T+35s in demos |

---

## Architecture

```
User (Telegram)
      │
      ▼
┌─────────────────────────────────────────────────────┐
│            OpenClaw Gateway                         │
│  7 bots, one per agent — each has its own token     │
│  and appears as an independent participant in the   │
│  Telegram group.                                    │
└──────────┬──────────────────────────────────────────┘
           │ agentToAgent tool / heartbeat / broadcast
    ┌──────┴───────────────────────────────────┐
    │           Agent Swarm                    │
    │                                          │
    │  orchestrator  ──── broadcasts to ───►  │
    │  cctv-bandung  marketplace  parts        │
    │  sosmed        polisi       report       │
    └──────────────────────────────────────────┘
           │ MCP stdio calls
    ┌──────┴────────────────────────────────────────┐
    │               MCP Servers                     │
    │                                               │
    │  browser-mcp   Playwright CCTV + marketplace  │
    │  vision-mcp    Jina CLIP v2 + Claude Haiku    │
    │  db-mcp        SQLite findings store          │
    │  a2a-mcp       Agent-to-agent inbox (SQLite)  │
    │  polisi-mcp    Police report template render  │
    └───────────────────────────────────────────────┘
```

### Two-Stage Vision Pipeline

```
candidate image
      │
      ▼
[Stage 1] Jina CLIP v2 cosine similarity
   < 0.55  → drop silently
  0.55–0.70 → log only
   ≥ 0.70  → ▼
[Stage 2] Claude Sonnet 4.6 vision reasoning
   → structured JSON: match_confidence, matches[],
     mismatches[], suspicious_signals[], narrative, route_to[]
```

Stage 1 costs ~$0.001/call via the Jina API.
Stage 2 (Sonnet) is only invoked on high-similarity candidates.

### Agent-to-Agent (A2A) Protocol

Agents share a lightweight inbox backed by SQLite (`a2a_messages` table).
Each message carries a `chain_id` to detect and break cycles, a `ttl_ticks`
counter that auto-expires stale tips, and a `case_id` scoping it to the
active investigation.

Workers follow this protocol on every heartbeat tick:

1. `list_inbox` — consume pending A2A messages
2. Act on tips (re-run targeted search, escalate to group)
3. `ttl_decrement` own queue
4. `a2a_send` route_to targets from Sonnet reasoning
5. Mark tick done

---

## Agentic Capabilities

### OpenClaw primitives used

| Primitive | How Lacakin uses it |
|---|---|
| `heartbeat` | Each worker runs on its own cadence (`HB_CCTV`, `HB_MARKETPLACE`, …) interpolated from the env file — 30s demo / 5m prod |
| `broadcast` | Orchestrator posts intake confirmations to the full swarm simultaneously |
| `agentToAgent` | Cross-agent tipping (CCTV → marketplace location hint, marketplace → parts suspicion) |
| `identity` | Each bot has a persona name, avatar, and role description visible in the Telegram group |
| `groupChat.mentionPatterns` | Orchestrator watches for `@lacakin` and case keywords |
| `thinkingDefault` | Sonnet extended-thinking enabled for orchestrator and report agents |

### Swarm awakening

On case intake the orchestrator sends four sequential `initial_sweep` A2A
pings (ttl=1) to all workers. This causes them to post opening lines in the
group within seconds, giving the impression of a live coordinated team
springing into action.

### Fixture-cached demo

`scripts/register_demo_fixtures.py` pre-registers SHA-256-keyed Sonnet
responses for staged demo images. On demo day the CCTV agent fires its
fixture at T+35s (match_confidence=0.86) and the marketplace agent fires at
T+75s (0.91), guaranteeing a full detection narrative without live API calls
for the vision stage.

---

## Repository Layout

```
lacakin-ai/
├── openclaw/
│   ├── agents.json5             # OpenClaw gateway config (7 bots, all wiring)
│   └── prompts/                 # System prompts + HEARTBEAT.md per agent
│       ├── A2A_PROTOCOL.md      # Shared protocol injected into all workers
│       └── main_system.md       # Orchestrator prompt (swarm awakening logic)
├── mcp/
│   ├── browser_mcp/             # Playwright: CCTV + marketplace scraping
│   ├── vision_mcp/              # Jina CLIP v2 match + Claude Haiku plate OCR
│   │   ├── server.py            # match_image, read_plate, reason_about_candidate
│   │   ├── sonnet_reason.py     # Stage-2 Claude Sonnet vision reasoning
│   │   └── fixture_cache.py     # SHA-256-keyed demo fixture store
│   ├── db_mcp/                  # Shared findings store (SQLite)
│   ├── a2a_mcp/                 # Agent-to-agent inbox (SQLite + TTL + cycle check)
│   └── polisi_mcp/              # Police report template renderer
├── demo_assets/
│   ├── reference/               # honda-beat-reference.jpg (provided by victim)
│   └── cctv_clips/              # Staged frames + static HTML for demo CCTV
├── shared/
│   ├── CONTEXT.md               # Live case context (orchestrator writes)
│   └── findings/                # Workers append findings here
├── tests/                       # pytest suite (12 tests, no API calls needed)
├── scripts/
│   ├── setup_vps.sh             # Full VPS bootstrap
│   ├── seed_demo.py             # Creates demo case + fake Tokopedia listing
│   ├── register_demo_fixtures.py # Pre-caches Sonnet responses for demo
│   └── smoke_e2e.py             # 4-check sanity script
├── .env.demo                    # Demo cadences (30s/45s/60s/45s/90s)
├── .env.prod                    # Prod cadences (5m/10m/15m/10m/30m)
└── requirements.txt
```

---

## How to Reproduce

### Prerequisites

- Python 3.10–3.12 (3.13 works but some deps lag behind)
- Node.js 18+ (for OpenClaw gateway)
- A Linux VPS (tested on Ubuntu 22.04)
- 7 Telegram bots created via [@BotFather](https://t.me/BotFather)
- API keys: `ANTHROPIC_API_KEY`, `JINA_API_KEY`

### 1. Clone and install

```bash
git clone https://github.com/<your-org>/lacakin-ai
cd lacakin-ai
pip install -r requirements.txt
playwright install chromium
```

### 2. Create Telegram bots

Create 7 bots via BotFather (one per agent):

```
orchestrator, cctv-bandung, marketplace, parts, sosmed, polisi, report
```

Disable group privacy for all bots (`/setprivacy → Disable`).

### 3. Configure environment

Copy `.env.demo` and fill in real values:

```bash
cp .env.demo .env
```

Add to `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
JINA_API_KEY=jina_...
TELEGRAM_TOKEN_ORCHESTRATOR=...
TELEGRAM_TOKEN_CCTV=...
TELEGRAM_TOKEN_MARKETPLACE=...
TELEGRAM_TOKEN_PARTS=...
TELEGRAM_TOKEN_SOSMED=...
TELEGRAM_TOKEN_POLISI=...
TELEGRAM_TOKEN_REPORT=...
LACAKIN_GROUP_ID=-100...        # numeric ID of your Telegram group
LACAKIN_SHARED=/opt/lacakin/shared
LACAKIN_DB=/opt/lacakin/lacakin.db
```

### 4. Place demo assets

```
demo_assets/reference/honda-beat-reference.jpg   ← victim's reference photo
demo_assets/cctv_clips/staged-motor-frame.jpg    ← pre-staged CCTV frame
```

### 5. Bootstrap VPS

```bash
bash scripts/setup_vps.sh          # installs openclaw, node deps
python scripts/seed_demo.py        # creates demo case in CONTEXT.md + findings/
python scripts/register_demo_fixtures.py  # pre-caches Sonnet responses
```

### 6. Validate OpenClaw config

```bash
openclaw validate --config openclaw/agents.json5
```

### 7. Start

```bash
# Demo mode (fast heartbeats)
source .env.demo && source .env
openclaw start --config openclaw/agents.json5

# Prod mode
source .env.prod && source .env
openclaw start --config openclaw/agents.json5
```

Add all 7 bots to your Telegram group, then message:

```
@lacakin motor saya dicuri! Honda Beat merah, plat D 4821 ZX,
terakhir di Jl. Dago simpang pukul 22:30 semalam.
```

### 8. Run tests

```bash
pytest -v -m "not needs_api"      # 12 tests, no API keys required
pytest -v                         # full suite (needs ANTHROPIC_API_KEY + JINA_API_KEY)
```

---

## Team Split (Hackathon)

| Person | Owns |
|---|---|
| **A** | `openclaw/` — gateway config, prompts, Telegram binding, swarm awakening, demo flow |
| **B** | `mcp/` — five Python MCP servers (browser, vision, db, a2a, polisi) |
| **C** | `scripts/`, report agent prompt, demo seed data, demo fixtures, recording |
