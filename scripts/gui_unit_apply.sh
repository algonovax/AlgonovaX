#!/usr/bin/env bash
set -euo pipefail

UNIT="$HOME/.config/systemd/user/algonovax-gui.service"
DROPIN_DIR="$HOME/.config/systemd/user/algonovax-gui.service.d"

mkdir -p "$(dirname "$UNIT")" "$DROPIN_DIR"

cat > "$UNIT" <<'UNITEOF'
[Unit]
Description=AlgoNovaX GUI (NiceGUI 8790)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
WorkingDirectory=%h/AlgonovaX

Environment=ALGONOVAX_PROJECT_DIR=%h/AlgonovaX
Environment=ALGONOVAX_GUI_HOST=127.0.0.1
Environment=ALGONOVAX_GUI_PORT=8790

ExecStart=%h/AlgonovaX/.venv/bin/python -m algonovax.gui.app
Restart=on-failure
RestartSec=2

NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=default.target
UNITEOF

cat > "$DROPIN_DIR/health.conf" <<'DROPEOF'
[Service]
ExecStartPost=%h/AlgonovaX/scripts/healthcheck_gui.sh
DROPEOF

systemctl --user daemon-reload
systemctl --user enable --now algonovax-gui.service
systemctl --user restart algonovax-gui.service
systemctl --user is-active --quiet algonovax-gui.service

echo "GUI_UNIT_APPLY_OK"
