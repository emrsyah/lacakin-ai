#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:-demo}"
ENV_FILE=".env.${PROFILE}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing $ENV_FILE" >&2; exit 1
fi
set -a
source "$ENV_FILE"
set +a
echo "Starting gateway with profile=$LACAKIN_PROFILE, HB_CCTV=$HB_CCTV"
exec openclaw gateway start
