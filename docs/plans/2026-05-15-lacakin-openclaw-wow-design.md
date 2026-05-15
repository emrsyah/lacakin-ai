# Lacakin on OpenClaw — Design Doc

**Date:** 2026-05-15
**Context:** 12h hackathon (Agenthon), 3 people, Bandung scope, VPS available.
**Status:** Approved by user. Implementation plan to follow via `writing-plans`.

---

## Goal

Build a multi-agent stolen-motorcycle tracker that demonstrates OpenClaw's
unique capabilities so vividly that judges remember the demo. The product
solves a real Indonesian problem (curanmor + slow police response) by giving
a victim a coordinated AI investigation team in 30 seconds — multiple
specialist agents that watch CCTVs, monitor marketplaces, hunt for parts,
draft police reports, all coordinating live in a single Telegram group.

## What makes this OpenClaw-native (not just a multi-agent app)

We leverage OpenClaw primitives that don't exist in plain LangChain/LangGraph:

1. **Multi-bot binding into one group** — 7 Telegram bots, each bound to a
   distinct agent via OpenClaw `channels.telegram.accounts` + `bindings`.
2. **`broadcast` config** — multiple agents post into the same group chat,
   each appearing as its own Telegram bot identity (name, avatar, about-text).
3. **Per-agent personas** — `identity` block sets name, theme, emoji, avatar.
4. **`tools.agentToAgent`** — workers DM each other via OpenClaw's primitive,
   with TTL + cycle protection in our prompt logic.
5. **`heartbeat` per agent** — each worker runs on its own cadence; switched
   between PROD and DEMO profiles via env interpolation.
6. **`groupChat.mentionPatterns`** — user @-mentions (`@mata`) route inbound
   to the correct agent's tick instead of orchestrator.
7. **Cron** — Pencatat Laporan generates periodic reports via OpenClaw cron.
8. **`thinkingDefault` per agent** — orchestrator + vision reasoning use
   "high"; routine ticks use "off". Token cost optimized.
9. **MCP servers** — custom Python MCP servers for browser, vision (CLIP +
   Sonnet vision + OCR), DB.
10. **`tools.allow/deny` per agent** — each persona has a tight tool surface.

## Architecture

```
                  ┌────────────────────────────────────────────┐
                  │  Telegram group "Lacakin · <case>"         │
                  │  Members: user + 7 bot accounts            │
                  └────────────────────────────────────────────┘
                                      ▲
                                      │ inbound + outbound per-bot
                                      ▼
            ┌───────────────────────────────────────────────────┐
            │  OpenClaw Gateway                                 │
            │  bindings: 1 Telegram account → 1 agent           │
            │  broadcast: group_id → [worker agents]            │
            │  tools.agentToAgent: enabled, allowlisted         │
            └───────────────────────────────────────────────────┘
                ▲              ▲              ▲              ▲
            heartbeat      heartbeat      heartbeat        cron
            (30s demo)     (45s demo)     (60s demo)      (90s demo)
                │              │              │              │
            ┌───┴──────────┐ ┌─┴────────┐ ┌──┴────────┐ ┌──┴────────┐
            │ cctv worker  │ │ market   │ │ parts     │ │ report    │
            │ + sosmed     │ │ worker   │ │ worker    │ │ worker    │
            └──────────────┘ └──────────┘ └───────────┘ └───────────┘
                  │                │             │
                  ▼                ▼             ▼
            ┌─────────────────────────────────────┐
            │  MCP servers (Python stdio)         │
            │  • browser-mcp (Playwright)         │
            │  • vision-mcp                       │
            │    – clip_match() — cheap filter    │
            │    – reason_about_candidate()       │
            │       (Claude Sonnet vision call)   │
            │    – read_plate() — PaddleOCR       │
            │  • db-mcp (SQLite, case + findings) │
            └─────────────────────────────────────┘

  Shared workspace symlink: ~/lacakin/shared/{CONTEXT.md, findings/, photos/}
```

## Agent roster

Seven agents total. Orchestrator is bound to its own bot but does not appear
in the `broadcast` list — it posts only when it actively chooses to address
the group.

| Agent ID | Bot username | Display name | Emoji | Role |
|---|---|---|---|---|
| `orchestrator` | `@lacakin_bot` | Lacakin | 🛵 | Intake, case context, summoning helper agents |
| `cctv-bandung` | `@mata_bandung_bot` | Mata Bandung | 👁️ | Sweep pelindung CCTVs near last-seen location |
| `marketplace` | `@pasar_bot` | Pemantau Pasar | 🛒 | Tokopedia + OLX listing scanner |
| `parts` | `@cadang_bot` | Pemburu Suku Cadang | 🔧 | Hunt for the motor sold piece-by-piece |
| `sosmed` | `@sosmed_bot` | Pengintai Sosmed | 📱 | Facebook Marketplace + Instagram |
| `polisi` | `@polisi_ai_bot` | Polisi-AI | 👮 | Drafts a *laporan kehilangan kendaraan bermotor* template |
| `report` | `@laporan_bot` | Pencatat Laporan | 📋 | Periodic + on-demand structured synthesis |

Each agent has a distinct voice encoded in its system prompt (Mata Bandung =
short observational, Pasar = market-trader cadence, Polisi-AI = birokratis,
etc.) — see section 2 of the brainstorming transcript for the full list.

## OpenClaw config sketch

```json5
{
  channels: {
    telegram: {
      enabled: true,
      accounts: {
        orchestrator: { token: "${TELEGRAM_TOKEN_ORCHESTRATOR}" },
        cctv:         { token: "${TELEGRAM_TOKEN_CCTV}" },
        marketplace:  { token: "${TELEGRAM_TOKEN_MARKETPLACE}" },
        parts:        { token: "${TELEGRAM_TOKEN_PARTS}" },
        sosmed:       { token: "${TELEGRAM_TOKEN_SOSMED}" },
        polisi:       { token: "${TELEGRAM_TOKEN_POLISI}" },
        report:       { token: "${TELEGRAM_TOKEN_REPORT}" },
      },
    },
  },
  bindings: [
    { agentId: "orchestrator", match: { channel: "telegram", accountId: "orchestrator" } },
    { agentId: "cctv-bandung", match: { channel: "telegram", accountId: "cctv" } },
    { agentId: "marketplace",  match: { channel: "telegram", accountId: "marketplace" } },
    { agentId: "parts",        match: { channel: "telegram", accountId: "parts" } },
    { agentId: "sosmed",       match: { channel: "telegram", accountId: "sosmed" } },
    { agentId: "polisi",       match: { channel: "telegram", accountId: "polisi" } },
    { agentId: "report",       match: { channel: "telegram", accountId: "report" } },
  ],
  broadcast: {
    "${LACAKIN_GROUP_ID}": [
      "cctv-bandung","marketplace","parts","sosmed","polisi","report",
    ],
  },
  tools: {
    agentToAgent: {
      enabled: true,
      allow: ["orchestrator","cctv-bandung","marketplace","parts","sosmed","polisi","report"],
    },
  },
  agents: {
    defaults: {
      sandbox: { mode: "non-main", scope: "session" },
      heartbeat: { every: "0m" },
      model: "anthropic/claude-haiku-4-5-20251001",
    },
    list: [
      { id: "orchestrator", model: "anthropic/claude-opus-4-7",
        thinkingDefault: "high", identity: { name: "Lacakin", emoji: "🛵" },
        groupChat: { mentionPatterns: ["@lacakin_bot","@lacakin"] }, ... },
      { id: "cctv-bandung",
        thinkingDefault: "off",
        heartbeat: { every: "${HB_CCTV}", lightContext: true,
          prompt: "Run a CCTV tick. Read CONTEXT.md and agent-to-agent inbox first." },
        identity: { name: "Mata Bandung", emoji: "👁️" },
        groupChat: { mentionPatterns: ["@mata_bandung_bot","@mata"] }, ... },
      // ... same shape for marketplace/parts/sosmed/polisi/report
    ],
  },
}
```

## Vision-reasoning pipeline

Two-stage filter — cheap CLIP cosine first, expensive Sonnet vision call only
on candidates that pass.

**Stage 1 — CLIP filter (local, ~50ms, zero token cost):**
- `clip_match(reference_path, candidate_path)` returns 0..1.
- < 0.55: drop silently.
- 0.55–0.70: log only, do not post.
- ≥ 0.70: advance to stage 2.

**Stage 2 — Sonnet vision (~2-4s, ~$0.008/call):**
`vision-mcp.reason_about_candidate(image_path, context_md, source_type)`
sends the image + case context to Claude Sonnet, returns structured JSON:

```json
{
  "match_confidence": 0.86,
  "matches": ["bullet point apa yang cocok"],
  "mismatches": [],
  "suspicious_signals": ["plat dikaburkan", "harga di bawah pasar"],
  "narrative": "1-2 kalimat alasan utama",
  "route_to": [{ "agent": "cadang", "reason": "motor heading south" }]
}
```

Worker posts to group when `match_confidence >= 0.75` AND `len(matches) >= 2`.
Posts include the image + bullets + optional @-mention from `route_to`.

Cost budget: 4 workers × ~3 stage-2 calls/tick × demo length 10 min ≈ $5-10
worst case for the whole demo run.

## Inter-agent @-mention protocol

Two mechanisms, used in tandem:

1. **Visible @-mention in the group** (theater): worker's group post ends
   with `@cadang — motor menuju selatan...` when Sonnet's `route_to` is set.
2. **Real agent-to-agent DM** (substance): worker also fires OpenClaw's
   `send_to_agent(agentId, message)`. Receiving agent checks A2A inbox at the
   start of each tick and overrides default sweep plan.

**Guardrails:**
- Pivot requests TTL = 2 ticks. After that, default plan resumes.
- Each `route_to` carries a `chain_id` UUID. Receiving agents won't forward
  the same chain back to its origin within the TTL.
- `close_case` can only be issued by the orchestrator.

**User-driven redirect:** `@mata cek Pasteur sekarang` typed in the group
routes via `mentionPatterns` to the worker's next tick as an A2A-style pivot
from "user". Same code path, same TTL.

## Cadence — two profiles via env

| Agent | PROD | **DEMO** |
|---|---|---|
| cctv-bandung | 5m | **30s** |
| marketplace | 10m | **45s** |
| parts | 15m | **60s** |
| sosmed | 10m | **45s** |
| polisi | on-demand | on-demand |
| report cron | 30m | **90s** |

Offsets (30/45/60s) intentional: avoids 4-bot post storms, creates a steady
drip during the demo.

**Cold-start "swarm awakening":** when orchestrator finishes intake, it
immediately A2A-pings every worker with `pivot: "initial_sweep"`. Within 5
seconds, all four workers post their opening message in sequence. Judges see
the swarm wake up.

**`heartbeat.skipWhenBusy: true`** prevents thundering herd if a tick hangs.

## Demo script (90 seconds)

See full transcript in section 7 of the brainstorming dialogue. Story beats:

1. **T+0:00** — One-line problem statement.
2. **T+0:05** — User types case in group; Lacakin asks one follow-up.
3. **T+0:25** — Lacakin pins case summary; 4 workers post opening lines in
   sequence (swarm awakening).
4. **T+0:35** — **Mata Bandung posts CCTV finding with full Sonnet
   reasoning.** The high-leverage vision moment.
5. **T+1:00** — Pemburu Suku Cadang acts on the @-mention from CCTV;
   Pasar follows with a Tokopedia listing finding (also with reasoning).
6. **T+1:15** — User types `@mata cek Pasteur` and the worker redirects live.
7. **T+1:25** — `@laporan rangkum`, then `@polisi tolong draft laporan polisi`.
8. **T+1:40** — Close.

**Pre-staging:** one CCTV camera URL is swapped to a pre-recorded clip
containing a matching motor, guaranteeing the T+0:35 moment fires. Fake
Tokopedia listing served from the VPS at a stable URL. Reference photo
matches both pre-staged assets via CLIP.

## Risks & pre-committed cutlines

| Risk | Detection | Mitigation |
|---|---|---|
| Pelindung CCTV blocked / video-only | H1 smoke | Swap to pre-recorded clips served from VPS |
| Tokopedia/OLX selectors broken | H1 / H10 | Fake Tokopedia listing is primary signal |
| 6 bots feel spammy in group | H7 rehearsal | Drop sosmed + polisi to "on-demand only" |
| Sonnet vision call slow | H8 timing | Fixture cache for the staged CCTV image (hash-keyed); real vision still works for other candidates |
| OpenClaw multi-bot broadcast misbehaves | H2 | Fall back to single-bot prefixed messages (`👁️ Mata Bandung:` then text) |

**Cut order if behind schedule:**

| Behind | Drop |
|---|---|
| 1h | parts agent |
| 2h | sosmed agent |
| 3h | A2A real DM (keep visible @-mentions theater only) |
| 4h | report cron + polisi periodic (on-demand only) |
| 5h | pinned case summary |

**Never cut:** CCTV worker, marketplace worker, vision-reasoning pipeline,
orchestrator intake flow, demo-mode short ticks.

## What we're NOT building (YAGNI)

- WhatsApp channel (Telegram only)
- ElevenLabs TTS / voice notes
- Live canvas / map UI
- Lacakin packaged as a reusable OpenClaw skills layer
- Multi-channel mirroring (WA + TG simultaneously)
- Multi-model `{primary, fallbacks}` config (single model per agent is fine
  for a 12h demo)
- Per-worker Docker sandboxing (default `non-main` session sandbox is enough)
- Real police integration (Polisi-AI is template-only)
- Authentication, multi-user, persistence beyond the case
- Anything that requires real Indonesian government API access

## Implementation hand-off

Next step: invoke `writing-plans` to produce a step-by-step implementation
plan from this design. Save the plan to
`docs/superpowers/plans/2026-05-15-lacakin-openclaw-wow.md`.

The three-person split for the plan:
- **A**: OpenClaw gateway, agent configs, Telegram bot accounts, intake/orchestrator prompt, demo group setup
- **B**: MCP servers (browser, vision with Sonnet pipeline, db), CLIP/OCR
- **C**: Worker HEARTBEAT prompts, A2A protocol logic, demo pre-staging assets, demo script + recording
