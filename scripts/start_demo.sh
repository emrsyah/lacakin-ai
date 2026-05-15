#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

ENV_FILE=".env.demo"
[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 1; }
set -a; source "$ENV_FILE"; set +a
[[ -f .env ]] && { set -a; source .env; set +a; }

PORT="${LACAKIN_ASSET_PORT:-8765}"
ASSET_LOG="${LACAKIN_ASSET_LOG:-/tmp/lacakin-assets.log}"
ASSET_PID_FILE="${LACAKIN_ASSET_PID:-/tmp/lacakin-assets.pid}"

if [[ -f "$ASSET_PID_FILE" ]] && kill -0 "$(cat "$ASSET_PID_FILE")" 2>/dev/null; then
  kill "$(cat "$ASSET_PID_FILE")" 2>/dev/null || true
fi
if command -v lsof >/dev/null 2>&1; then
  HOLDERS="$(lsof -ti:"$PORT" 2>/dev/null || true)"
  if [[ -n "$HOLDERS" ]]; then
    echo "Releasing port $PORT (pids: $HOLDERS)"
    echo "$HOLDERS" | xargs -r kill 2>/dev/null || true
    sleep 0.5
  fi
fi

PY="${PYTHON:-python3}"
if [[ -x "$REPO/.venv/bin/python3" ]]; then
  PY="$REPO/.venv/bin/python3"
fi

echo "[1/4] Asset server on port $PORT"
nohup "$PY" scripts/serve_demo_assets.py >"$ASSET_LOG" 2>&1 &
echo $! >"$ASSET_PID_FILE"
sleep 1

echo "[2/4] Seeding case context"
"$PY" scripts/seed_demo.py

echo "[3/4] Registering verified imagery"
"$PY" scripts/register_demo_fixtures.py

echo "[4/4] Smoke check"
"$PY" scripts/smoke_e2e.py

cat <<EOF

Lacakin ready. Asset server PID $(cat "$ASSET_PID_FILE"), logs at $ASSET_LOG.
Open Telegram and send to @lacakin_bot:

  Motor saya dicuri! Honda Beat 2022 merah-hitam, plat D 1234 ABC,
  terakhir di Dago Simpang jam 14:00. Ada stiker MotoGP di tangki,
  velg racing aftermarket warna emas.

EOF

exec bash scripts/start_gateway.sh demo
