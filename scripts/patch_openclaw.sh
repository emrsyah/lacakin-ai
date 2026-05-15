#!/usr/bin/env bash
# Patch Lacakin agents into ~/.openclaw/openclaw.json
# Run once after setup_vps.sh and filling .env.demo.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO/.env.demo"

[[ -f "$ENV_FILE" ]] || { echo "Error: $ENV_FILE not found — fill it in first"; exit 1; }
set -a; source "$ENV_FILE"; set +a

VENV_PY="$REPO/.venv/bin/python3"
[[ -x "$VENV_PY" ]] || { echo "Error: venv missing — run setup_vps.sh first"; exit 1; }

# Guard: skip if already patched
if openclaw config get agents.list --json 2>/dev/null \
   | python3 -c "import json,sys; ids=[x.get('id') for x in json.load(sys.stdin)]; exit(0 if 'orchestrator' in ids else 1)" 2>/dev/null; then
  echo "Lacakin agents already present. Nothing to do."
  exit 0
fi

N=$(openclaw config get agents.list --json 2>/dev/null \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
echo "Existing agents: $N — appending 7 Lacakin agents"

# 1. Telegram multi-account bot tokens
echo "[1/4] Patching telegram accounts..."
openclaw config set "channels.telegram.accounts.orchestrator.botToken" "$TELEGRAM_TOKEN_ORCHESTRATOR"
openclaw config set "channels.telegram.accounts.cctv.botToken"         "$TELEGRAM_TOKEN_CCTV"
openclaw config set "channels.telegram.accounts.marketplace.botToken"  "$TELEGRAM_TOKEN_MARKETPLACE"
openclaw config set "channels.telegram.accounts.parts.botToken"        "$TELEGRAM_TOKEN_PARTS"
openclaw config set "channels.telegram.accounts.sosmed.botToken"       "$TELEGRAM_TOKEN_SOSMED"
openclaw config set "channels.telegram.accounts.polisi.botToken"       "$TELEGRAM_TOKEN_POLISI"
openclaw config set "channels.telegram.accounts.report.botToken"       "$TELEGRAM_TOKEN_REPORT"

# 2. MCP servers (use venv python so imports resolve without activating venv)
echo "[2/4] Patching MCP servers..."
openclaw config patch --stdin << EOF
{
  "mcp": {
    "servers": {
      "lacakin-browser-mcp": { "command": "$VENV_PY", "args": ["-m","mcp.browser_mcp.server"], "cwd": "$REPO" },
      "lacakin-vision-mcp":  { "command": "$VENV_PY", "args": ["-m","mcp.vision_mcp.server"],  "cwd": "$REPO" },
      "lacakin-db-mcp":      { "command": "$VENV_PY", "args": ["-m","mcp.db_mcp.server"],      "cwd": "$REPO" },
      "lacakin-a2a-mcp":     { "command": "$VENV_PY", "args": ["-m","mcp.a2a_mcp.server"],     "cwd": "$REPO" },
      "lacakin-polisi-mcp":  { "command": "$VENV_PY", "args": ["-m","mcp.polisi_mcp.server"],  "cwd": "$REPO" }
    }
  }
}
EOF

# 3. Bindings (agent → telegram account) + broadcast (group → agents)
echo "[3/4] Patching bindings + broadcast..."
openclaw config set "bindings" --json '[
  {"agentId":"orchestrator","match":{"channel":"telegram","accountId":"orchestrator"}},
  {"agentId":"cctv-bandung","match":{"channel":"telegram","accountId":"cctv"}},
  {"agentId":"marketplace", "match":{"channel":"telegram","accountId":"marketplace"}},
  {"agentId":"parts",       "match":{"channel":"telegram","accountId":"parts"}},
  {"agentId":"sosmed",      "match":{"channel":"telegram","accountId":"sosmed"}},
  {"agentId":"polisi",      "match":{"channel":"telegram","accountId":"polisi"}},
  {"agentId":"report",      "match":{"channel":"telegram","accountId":"report"}}
]'

openclaw config set "broadcast.$LACAKIN_GROUP_ID" --json \
  '["cctv-bandung","marketplace","parts","sosmed","polisi","report"]'

# 4. Agents
echo "[4/4] Adding 7 agents..."

# Orchestrator — uses Sonnet (more capable, already in config)
I=$N
openclaw config set "agents.list[$I].id"            "orchestrator"
openclaw config set "agents.list[$I].workspace"     "$HOME/lacakin/workspace-main"
openclaw config set "agents.list[$I].model.primary" "openrouter/anthropic/claude-sonnet-4.5"
openclaw config set "agents.list[$I].prompt"        "Anda Lacakin. Baca ./SYSTEM.md untuk instruksi."
openclaw config set "agents.list[$I].mcp"           --json '["lacakin-db-mcp","lacakin-a2a-mcp"]'

# CCTV
I=$((N+1))
openclaw config set "agents.list[$I].id"              "cctv-bandung"
openclaw config set "agents.list[$I].workspace"       "$HOME/lacakin/workspace-cctv"
openclaw config set "agents.list[$I].heartbeat.every" "$HB_CCTV"
openclaw config set "agents.list[$I].mcp"             --json '["lacakin-browser-mcp","lacakin-vision-mcp","lacakin-db-mcp","lacakin-a2a-mcp"]'

# Marketplace
I=$((N+2))
openclaw config set "agents.list[$I].id"              "marketplace"
openclaw config set "agents.list[$I].workspace"       "$HOME/lacakin/workspace-marketplace"
openclaw config set "agents.list[$I].heartbeat.every" "$HB_MARKETPLACE"
openclaw config set "agents.list[$I].mcp"             --json '["lacakin-browser-mcp","lacakin-vision-mcp","lacakin-db-mcp","lacakin-a2a-mcp"]'

# Parts
I=$((N+3))
openclaw config set "agents.list[$I].id"              "parts"
openclaw config set "agents.list[$I].workspace"       "$HOME/lacakin/workspace-parts"
openclaw config set "agents.list[$I].heartbeat.every" "$HB_PARTS"
openclaw config set "agents.list[$I].mcp"             --json '["lacakin-browser-mcp","lacakin-vision-mcp","lacakin-db-mcp","lacakin-a2a-mcp"]'

# Sosmed
I=$((N+4))
openclaw config set "agents.list[$I].id"              "sosmed"
openclaw config set "agents.list[$I].workspace"       "$HOME/lacakin/workspace-sosmed"
openclaw config set "agents.list[$I].heartbeat.every" "$HB_SOSMED"
openclaw config set "agents.list[$I].mcp"             --json '["lacakin-browser-mcp","lacakin-vision-mcp","lacakin-db-mcp","lacakin-a2a-mcp"]'

# Polisi (no heartbeat — on-demand only)
I=$((N+5))
openclaw config set "agents.list[$I].id"        "polisi"
openclaw config set "agents.list[$I].workspace" "$HOME/lacakin/workspace-polisi"
openclaw config set "agents.list[$I].mcp"       --json '["lacakin-db-mcp","lacakin-polisi-mcp"]'

# Report — uses Sonnet
I=$((N+6))
openclaw config set "agents.list[$I].id"              "report"
openclaw config set "agents.list[$I].workspace"       "$HOME/lacakin/workspace-report"
openclaw config set "agents.list[$I].model.primary"   "openrouter/anthropic/claude-sonnet-4.5"
openclaw config set "agents.list[$I].heartbeat.every" "$HB_REPORT"
openclaw config set "agents.list[$I].mcp"             --json '["lacakin-db-mcp","lacakin-a2a-mcp"]'

echo ""
echo "Done. Validating config..."
openclaw config validate && echo "Config valid — run: bash scripts/start_gateway.sh"
