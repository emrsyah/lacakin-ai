#!/usr/bin/env bash
# One-shot VPS bring-up. Tested target: Ubuntu 22.04+.
set -euo pipefail

echo "[1/6] System deps"
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip nodejs git \
    libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2t64 libpango-1.0-0 \
    libcairo2 libxshmfence1

echo "[2/6] Python venv"
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip wheel
pip install -r requirements.txt

echo "[3/6] Playwright Chromium"
playwright install chromium
playwright install-deps chromium

echo "[4/6] OpenClaw gateway"
npm i -g @openclaw/cli || npm i -g openclaw   # whichever package name resolves
openclaw --version

echo "[5/6] Lacakin shared workspace"
mkdir -p ~/lacakin/shared/photos ~/lacakin/shared/findings
mkdir -p ~/lacakin/workspace-{main,cctv,tokopedia,olx,parts,report}
# symlink shared/ into each worker workspace so they all see CONTEXT.md + findings/
for w in cctv tokopedia olx parts report; do
  ln -sfn ~/lacakin/shared ~/lacakin/workspace-$w/shared
done
# CCTV worker also needs cameras.json next to it (for HEARTBEAT prompt to read).
cp mcp/browser_mcp/cameras.json ~/lacakin/workspace-cctv/cameras.json

echo "[6/6] Env"
cat <<EOF
Set these env vars before 'openclaw start':
  export OPENROUTER_API_KEY=sk-or-v1-...
  export TELEGRAM_TOKEN_ORCHESTRATOR=...
  export TELEGRAM_TOKEN_CCTV=...
  export TELEGRAM_TOKEN_MARKETPLACE=...
  export TELEGRAM_TOKEN_PARTS=...
  export TELEGRAM_TOKEN_SOSMED=...
  export TELEGRAM_TOKEN_POLISI=...
  export TELEGRAM_TOKEN_REPORT=...
  export LACAKIN_GROUP_ID=-100xxxxxxxxx
  export LACAKIN_SHARED=\$HOME/lacakin/shared
  export LACAKIN_DB=\$HOME/lacakin/lacakin.db

Then:
  bash scripts/start_gateway.sh demo   # or prod
EOF

echo "[7/7] Distributing prompts to agent workspaces"
mkdir -p ~/lacakin/workspace-{main,cctv,marketplace,parts,sosmed,polisi,report}

# A2A_PROTOCOL.md goes into every worker workspace (the heartbeat agents).
for w in cctv marketplace parts sosmed report; do
  cp openclaw/prompts/A2A_PROTOCOL.md ~/lacakin/workspace-$w/A2A_PROTOCOL.md
done

# Heartbeat prompts: one per worker, renamed to HEARTBEAT.md
cp openclaw/prompts/heartbeat_cctv.md         ~/lacakin/workspace-cctv/HEARTBEAT.md
cp openclaw/prompts/heartbeat_marketplace.md  ~/lacakin/workspace-marketplace/HEARTBEAT.md
cp openclaw/prompts/heartbeat_parts.md        ~/lacakin/workspace-parts/HEARTBEAT.md
cp openclaw/prompts/heartbeat_sosmed.md       ~/lacakin/workspace-sosmed/HEARTBEAT.md

# System prompts: orchestrator + polisi + report
cp openclaw/prompts/main_system.md   ~/lacakin/workspace-main/SYSTEM.md
cp openclaw/prompts/polisi_system.md ~/lacakin/workspace-polisi/SYSTEM.md
cp openclaw/prompts/report_system.md ~/lacakin/workspace-report/SYSTEM.md

# cctv-bandung also needs cameras.json next to it for the prompt to reference
cp mcp/browser_mcp/cameras.json ~/lacakin/workspace-cctv/cameras.json

# Re-symlink shared/ into each worker workspace
for w in main cctv marketplace parts sosmed polisi report; do
  ln -sfn ~/lacakin/shared ~/lacakin/workspace-$w/shared
done

echo "Prompts distributed. Re-run this script whenever prompts change."
