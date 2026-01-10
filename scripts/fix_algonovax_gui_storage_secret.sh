#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${ALGONOVAX_PROJECT_DIR:-${ALGONOVAX_ROOT:-$HOME/AlgonovaX}}"
APP_PY="$PROJECT_DIR/algonovax/gui/app.py"

die() { echo "ERROR: $*" >&2; exit 1; }

[ -d "$PROJECT_DIR" ] || die "Project dir not found: $PROJECT_DIR"
[ -f "$APP_PY" ] || die "app.py not found: $APP_PY"

ts="$(date +%Y%m%d_%H%M%S)"
cp -a "$APP_PY" "$APP_PY.bak.$ts"

python3 - <<'PY'
from __future__ import annotations
import sys
from pathlib import Path

app_py = Path(sys.argv[1])
txt = app_py.read_text(encoding="utf-8")

if "ui.run(" not in txt:
    raise SystemExit("ERROR: ui.run( not found in app.py")

# Quick no-op if already fixed
ui_idx = txt.find("ui.run(")
window = txt[ui_idx: ui_idx + 2000]
if "storage_secret=" in window or "storage_secret =" in window:
    print("OK: storage_secret already wired into ui.run()")
    raise SystemExit(0)

lines = txt.splitlines(True)

# Ensure `import os` exists (best-effort: insert after any future imports)
if "import os\n" not in lines and "import os\r\n" not in lines and "\nimport os\n" not in txt:
    insert_at = 0
    for i, line in enumerate(lines[:50]):
        if line.startswith("from __future__ import"):
            insert_at = i + 1
    lines.insert(insert_at, "import os\n")

# Find the ui.run line number
ui_line_idx = None
for i, line in enumerate(lines):
    if "ui.run(" in line:
        ui_line_idx = i
        break
if ui_line_idx is None:
    raise SystemExit("ERROR: ui.run( line not found after initial detection")

indent = lines[ui_line_idx].split("ui.run(")[0]
pre_block = [
    f"{indent}# Ensure NiceGUI user storage is enabled (required when using app.storage.user)\n",
    f"{indent}try:\n",
    f"{indent}    storage_secret = os.environ['ALGONOVAX_GUI_STORAGE_SECRET']\n",
    f"{indent}except KeyError as e:\n",
    f"{indent}    raise RuntimeError('ALGONOVAX_GUI_STORAGE_SECRET is not set') from e\n",
    "\n",
]
lines[ui_line_idx:ui_line_idx] = pre_block
ui_line_idx += len(pre_block)

# Walk forward to find the matching closing paren of ui.run( ... )
start_i = ui_line_idx
s = "".join(lines[start_i:])

start_pos = s.find("ui.run(")
if start_pos < 0:
    raise SystemExit("ERROR: unable to locate ui.run( in reconstructed content")

pos = start_pos
depth = 0
end_pos = None
while pos < len(s):
    ch = s[pos]
    if ch == "(":
        depth += 1
    elif ch == ")":
        depth -= 1
        if depth == 0:
            end_pos = pos
            break
    pos += 1

if end_pos is None:
    raise SystemExit("ERROR: could not find closing ')' for ui.run(...)")

# Determine the line that contains the closing ')'
before_end = s[:end_pos]
closing_line_offset = before_end.count("\n")
closing_line_idx = start_i + closing_line_offset

# Insert the parameter right before the closing paren line
arg_indent = indent + "    "
lines.insert(closing_line_idx, f"{arg_indent}storage_secret=storage_secret,\n")

app_py.write_text("".join(lines), encoding="utf-8")
print("OK: patched app.py to pass storage_secret into ui.run()")
PY "$APP_PY"

systemctl --user daemon-reload
systemctl --user restart algonovax-gui.service

echo
echo "VERIFY:"
echo "  curl -i http://127.0.0.1:8790/ | sed -n '1,15p'"
echo "  curl -i -u kalen:CHANGE_ME_NOW http://127.0.0.1:9443/ | sed -n '1,15p'"
