#!/usr/bin/env bash
set -euo pipefail

cd ~/projects/AlgonovaX
source .venv/bin/activate

python -m py_compile algonovax/gui/app.py

systemctl --user is-active --quiet algonovax-gui.service

curl -fsS --max-time 2 http://127.0.0.1:8790/ >/dev/null

echo "GUI_VERIFY_OK"
