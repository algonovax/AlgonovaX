#!/usr/bin/env bash
set -euo pipefail
cd "${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"

SRC="scripts/app_py.golden"
DST="algonovax/gui/app.py"
SVC="algonovax-gui.service"
PY="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/.venv/bin/python"

die(){ echo "ERROR: $*" >&2; exit 1; }
trap 'die "Failed at line $LINENO"' ERR

[[ -f "$SRC" ]] || die "Missing $SRC"
[[ -x "$PY" ]] || die "Missing venv python: $PY"

sudo install -o root -g root -m 0444 "$SRC" "$DST"
"$PY" -m py_compile "$DST"

systemctl --user daemon-reload >/dev/null 2>&1 || true
systemctl --user restart "$SVC"
systemctl --user is-active --quiet "$SVC" || die "$SVC not active"

echo "GUI_APPLY_OK"
