#!/usr/bin/env bash
# Patch Lacakin agents into ~/.openclaw/openclaw.json
# Run once after setup_vps.sh and filling .env.demo.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO/.env.demo"

[[ -f "$ENV_FILE" ]] || { echo "Error: $ENV_FILE not found — fill it in first"; exit 1; }
set -a; source "$ENV_FILE"; set +a

: "${HB_CCTV:=30s}"
: "${HB_MARKETPLACE:=45s}"
: "${HB_PARTS:=60s}"
: "${HB_SOSMED:=45s}"
: "${HB_REPORT:=90s}"
: "${TELEGRAM_OWNER_ID:=2058113332}"

VENV_PY="$REPO/.venv/bin/python3"
[[ -x "$VENV_PY" ]] || { echo "Error: venv missing — run setup_vps.sh first"; exit 1; }

# Guard: skip if already patched
if openclaw config get agents.list --json 2>/dev/null \
   | python3 -c "import json,sys; from pathlib import Path; required={'orchestrator','cctv','marketplace','parts','sosmed','polisi','report'}; ids={x.get('id') for x in json.load(sys.stdin)}; have_auth=all((Path.home()/'.openclaw'/'agents'/i/'agent'/'auth-profiles.json').exists() for i in required); exit(0 if required <= ids and have_auth else 1)" 2>/dev/null; then
  echo "Lacakin agents already present. Nothing to do."
  exit 0
fi

LACAKIN_IDS='["orchestrator","cctv","marketplace","parts","sosmed","polisi","report"]'

# Wipe any stale Lacakin state from previous failed runs (stale agent entries,
# stale broadcast keys) so OpenClaw config validation doesn't reject new writes.
# We edit the JSON file directly because `openclaw config delete` is a no-op
# for map keys, and `openclaw config set` would re-validate against stale state.
echo "[0/4] Cleaning up stale Lacakin config..."
python3 <<'PY'
import json
from pathlib import Path
cfg_path = Path.home() / '.openclaw' / 'openclaw.json'
if not cfg_path.exists():
    raise SystemExit(0)
cfg = json.loads(cfg_path.read_text())
cfg['broadcast'] = {}
lacakin = {'orchestrator','cctv','cctv-bandung','marketplace','parts','sosmed','polisi','report'}
agents = cfg.get('agents', {}).get('list', [])
cfg.setdefault('agents', {})['list'] = [a for a in agents if a.get('id') not in lacakin]
cfg_path.write_text(json.dumps(cfg, indent=2))
PY

N=$(openclaw config get agents.list --json 2>/dev/null \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
echo "Existing agents after cleanup: $N — appending 7 Lacakin agents"

# 1. Telegram multi-account bot tokens
echo "[1/4] Patching telegram accounts..."
openclaw config set "channels.telegram.accounts.orchestrator.botToken" "$TELEGRAM_TOKEN_ORCHESTRATOR"
openclaw config set "channels.telegram.accounts.cctv.botToken"         "$TELEGRAM_TOKEN_CCTV"
openclaw config set "channels.telegram.accounts.marketplace.botToken"  "$TELEGRAM_TOKEN_MARKETPLACE"
openclaw config set "channels.telegram.accounts.parts.botToken"        "$TELEGRAM_TOKEN_PARTS"
openclaw config set "channels.telegram.accounts.sosmed.botToken"       "$TELEGRAM_TOKEN_SOSMED"
openclaw config set "channels.telegram.accounts.polisi.botToken"       "$TELEGRAM_TOKEN_POLISI"
openclaw config set "channels.telegram.accounts.report.botToken"       "$TELEGRAM_TOKEN_REPORT"
openclaw config patch --stdin << EOF
{
  "channels": {
    "telegram": {
      "allowFrom": ["telegram:$TELEGRAM_OWNER_ID"],
      "groups": {
        "*": { "requireMention": true },
        "$LACAKIN_GROUP_ID": { "requireMention": true }
      },
      "accounts": {
        "orchestrator": { "groupPolicy": "allowlist", "allowFrom": ["telegram:$TELEGRAM_OWNER_ID"] },
        "cctv": { "groupPolicy": "allowlist", "allowFrom": ["telegram:$TELEGRAM_OWNER_ID"] },
        "marketplace": { "groupPolicy": "allowlist", "allowFrom": ["telegram:$TELEGRAM_OWNER_ID"] },
        "parts": { "groupPolicy": "allowlist", "allowFrom": ["telegram:$TELEGRAM_OWNER_ID"] },
        "sosmed": { "groupPolicy": "allowlist", "allowFrom": ["telegram:$TELEGRAM_OWNER_ID"] },
        "polisi": { "groupPolicy": "allowlist", "allowFrom": ["telegram:$TELEGRAM_OWNER_ID"] },
        "report": { "groupPolicy": "allowlist", "allowFrom": ["telegram:$TELEGRAM_OWNER_ID"] }
      }
    }
  }
}
EOF

# 2. MCP servers (use venv python so imports resolve without activating venv)
echo "[2/4] Patching MCP servers..."
openclaw config patch --stdin << EOF
{
  "mcp": {
    "servers": {
      "lacakin-browser-mcp": { "command": "$VENV_PY", "args": ["$REPO/mcp/browser_mcp/server.py"], "cwd": "/tmp" },
      "lacakin-vision-mcp":  { "command": "$VENV_PY", "args": ["$REPO/mcp/vision_mcp/server.py"],  "cwd": "/tmp" },
      "lacakin-db-mcp":      { "command": "$VENV_PY", "args": ["$REPO/mcp/db_mcp/server.py"],      "cwd": "/tmp" },
      "lacakin-a2a-mcp":     { "command": "$VENV_PY", "args": ["$REPO/mcp/a2a_mcp/server.py"],     "cwd": "/tmp" },
      "lacakin-polisi-mcp":  { "command": "$VENV_PY", "args": ["$REPO/mcp/polisi_mcp/server.py"],  "cwd": "/tmp" },
      "lacakin-ops-mcp":     { "command": "$VENV_PY", "args": ["$REPO/mcp/ops_mcp/server.py"],     "cwd": "/tmp" }
    }
  }
}
EOF

# 3. Agents (must come before bindings/broadcast so IDs exist for validation)
echo "[3/4] Adding 7 agents..."

# Orchestrator — uses Sonnet (more capable, already in config)
I=$N
openclaw config set "agents.list[$I].id"            "orchestrator"
openclaw config set "agents.list[$I].workspace"     "$HOME/lacakin/workspace-main"
openclaw config set "agents.list[$I].model.primary" "openrouter/free"

# CCTV
I=$((N+1))
openclaw config set "agents.list[$I].id"               "cctv"
openclaw config set "agents.list[$I].workspace"        "$HOME/lacakin/workspace-cctv"
openclaw config set "agents.list[$I].heartbeat.every"  "$HB_CCTV"
openclaw config set "agents.list[$I].heartbeat.prompt" "Run CCTV tick. Read ./A2A_PROTOCOL.md and ./HEARTBEAT.md for full instructions."

# Marketplace
I=$((N+2))
openclaw config set "agents.list[$I].id"               "marketplace"
openclaw config set "agents.list[$I].workspace"        "$HOME/lacakin/workspace-marketplace"
openclaw config set "agents.list[$I].heartbeat.every"  "$HB_MARKETPLACE"
openclaw config set "agents.list[$I].heartbeat.prompt" "Marketplace tick. Read ./A2A_PROTOCOL.md and ./HEARTBEAT.md."

# Parts
I=$((N+3))
openclaw config set "agents.list[$I].id"               "parts"
openclaw config set "agents.list[$I].workspace"        "$HOME/lacakin/workspace-parts"
openclaw config set "agents.list[$I].heartbeat.every"  "$HB_PARTS"
openclaw config set "agents.list[$I].heartbeat.prompt" "Parts tick. Read ./A2A_PROTOCOL.md and ./HEARTBEAT.md."

# Sosmed
I=$((N+4))
openclaw config set "agents.list[$I].id"               "sosmed"
openclaw config set "agents.list[$I].workspace"        "$HOME/lacakin/workspace-sosmed"
openclaw config set "agents.list[$I].heartbeat.every"  "$HB_SOSMED"
openclaw config set "agents.list[$I].heartbeat.prompt" "Social media tick. Read ./A2A_PROTOCOL.md and ./HEARTBEAT.md."

# Polisi (no heartbeat — on-demand only)
I=$((N+5))
openclaw config set "agents.list[$I].id"        "polisi"
openclaw config set "agents.list[$I].workspace" "$HOME/lacakin/workspace-polisi"

# Report — uses Sonnet
I=$((N+6))
openclaw config set "agents.list[$I].id"               "report"
openclaw config set "agents.list[$I].workspace"        "$HOME/lacakin/workspace-report"
openclaw config set "agents.list[$I].model.primary"    "openrouter/free"
openclaw config set "agents.list[$I].heartbeat.every"  "$HB_REPORT"
openclaw config set "agents.list[$I].heartbeat.prompt" "Generate periodic synthesis report. Read ./SYSTEM.md untuk instruksi lengkap."

# 4. Bindings + broadcast (after agents so IDs resolve in validation)
echo "[4/4] Patching bindings + broadcast..."
openclaw config set "bindings" --json '[
  {"agentId":"orchestrator","match":{"channel":"telegram","accountId":"orchestrator"}},
  {"agentId":"cctv",        "match":{"channel":"telegram","accountId":"cctv"}},
  {"agentId":"marketplace", "match":{"channel":"telegram","accountId":"marketplace"}},
  {"agentId":"parts",       "match":{"channel":"telegram","accountId":"parts"}},
  {"agentId":"sosmed",      "match":{"channel":"telegram","accountId":"sosmed"}},
  {"agentId":"polisi",      "match":{"channel":"telegram","accountId":"polisi"}},
  {"agentId":"report",      "match":{"channel":"telegram","accountId":"report"}}
]'

openclaw config set "broadcast.$LACAKIN_GROUP_ID" --json \
  '["cctv","marketplace","parts","sosmed","polisi","report"]'

if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  echo "Writing per-agent OpenRouter auth profiles..."
  python3 <<'PY'
import json
import os
from pathlib import Path

key = os.environ.get("OPENROUTER_API_KEY", "")
if not key:
    raise SystemExit(0)

payload = {
    "version": 1,
    "profiles": {
        "openrouter:default": {
            "type": "api_key",
            "provider": "openrouter",
            "key": key,
        }
    },
}

for agent_id in ["orchestrator", "cctv", "marketplace", "parts", "sosmed", "polisi", "report"]:
    agent_dir = Path.home() / ".openclaw" / "agents" / agent_id / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    auth_path = agent_dir / "auth-profiles.json"
    auth_path.write_text(json.dumps(payload, indent=2))
    auth_path.chmod(0o600)
PY
else
  echo "Warning: OPENROUTER_API_KEY is not set; per-agent model auth was not written."
fi

echo ""
echo "Done. Validating config..."
openclaw config validate && echo "Config valid — run: bash scripts/start_gateway.sh"
