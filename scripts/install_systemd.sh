#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT_NAME="lacakin.service"
SRC="$REPO/scripts/$UNIT_NAME"
DST="$UNIT_DIR/$UNIT_NAME"

[[ -f "$SRC" ]] || { echo "missing $SRC" >&2; exit 1; }

mkdir -p "$UNIT_DIR"
cp "$SRC" "$DST"

systemctl --user daemon-reload
systemctl --user enable "$UNIT_NAME"

if ! loginctl show-user "$USER" 2>/dev/null | grep -q '^Linger=yes'; then
  echo
  echo "Tip: enable user lingering so the service survives SSH logout / reboot:"
  echo "  sudo loginctl enable-linger $USER"
fi

cat <<EOF

Installed $DST.

Useful commands:
  systemctl --user start    lacakin       # run now
  systemctl --user stop     lacakin       # graceful stop (gateway + asset server)
  systemctl --user restart  lacakin
  systemctl --user status   lacakin
  journalctl --user -u lacakin -f         # follow live logs
  journalctl --user -u lacakin -n 200     # last 200 lines
  journalctl --user -u lacakin --since "10 min ago"

EOF
