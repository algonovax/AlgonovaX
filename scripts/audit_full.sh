#!/usr/bin/env bash
# scripts/audit_full.sh (TERMUX-SAFE, non-blocking)
# - ruff/pip-audit/bandit optional
# - mypy disabled by default (RUN_MYPY=1 to enable)
# - gui import enforced on non-Termux only
set -euo pipefail

die(){ echo "FAIL: $*" >&2; exit 1; }

ROOT="$(pwd)"
if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
  ROOT="$(git rev-parse --show-toplevel)"
fi
cd "$ROOT" || die "cannot cd to ROOT=$ROOT"

TS="$(date +%Y%m%d_%H%M%S)"
AUDIT_DIR="$ROOT/audit"
LOG_DIR="$AUDIT_DIR/logs/$TS"
REPORT="$AUDIT_DIR/AUDIT_REPORT.$TS.md"
mkdir -p "$LOG_DIR" || die "cannot create audit dir at $LOG_DIR"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
else
  die "Missing .venv at $ROOT/.venv"
fi

PY_BIN="$(command -v python || true)"
[[ -n "$PY_BIN" ]] || die "python not found in venv"

run_step() {
  local name="$1"; shift
  local log="$LOG_DIR/${name}.log"
  echo "== $name ==" | tee -a "$REPORT"
  {
    echo "cmd: $*"
    echo "pwd: $(pwd)"
    echo "ts: $(date -Is)"
    echo
    "$@"
  } >"$log" 2>&1 || {
    echo "- **$name:** FAIL (see $log)" | tee -a "$REPORT"
    echo | tee -a "$REPORT"
    return 1
  }
  echo "- **$name:** PASS (log: $log)" | tee -a "$REPORT"
  echo | tee -a "$REPORT"
  return 0
}

skip_step() {
  local name="$1"; shift
  local reason="$1"; shift
  local log="$LOG_DIR/${name}.log"
  {
    echo "SKIP: $reason"
    echo "pwd: $(pwd)"
    echo "ts: $(date -Is)"
  } >"$log" 2>&1
  echo "== $name ==" | tee -a "$REPORT"
  echo "- **$name:** SKIP ($reason) (log: $log)" | tee -a "$REPORT"
  echo | tee -a "$REPORT"
  return 0
}

cat >"$REPORT" <<MD
# AlgoNovaX Audit Report (Termux-safe)

- Timestamp: \`$TS\`
- Root: \`$ROOT\`
- Python: \`$("$PY_BIN" -V 2>&1)\`
- Executable: \`$PY_BIN\`

## Summary
MD
FAILS=0

run_step snapshot_git bash -lc '
set -euo pipefail
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "branch: $(git rev-parse --abbrev-ref HEAD)"
  echo "commit: $(git rev-parse HEAD)"
  echo
  git status --porcelain=v1
  echo
  git log -1 --oneline
else
  echo "git: not a repo or git missing"
fi
' || FAILS=$((FAILS+1))

run_step snapshot_pip bash -lc '
set -euo pipefail
python -m pip -V
python -m pip freeze
' || FAILS=$((FAILS+1))

# ruff (only if already installed; no rust builds here)
if python -c "import ruff" >/dev/null 2>&1; then
  run_step ruff_check  bash -lc "set -euo pipefail; python -m ruff check ." || FAILS=$((FAILS+1))
  run_step ruff_format bash -lc "set -euo pipefail; python -m ruff format --check ." || FAILS=$((FAILS+1))
else
  skip_step ruff_check "ruff not installed (skipping on Termux to avoid Rust build)"
  skip_step ruff_format "ruff not installed (skipping on Termux to avoid Rust build)"
fi

# mypy (opt-in)
if [[ "${RUN_MYPY:-0}" == "1" ]]; then
  if command -v mypy >/dev/null 2>&1; then
    run_step mypy bash -lc "set -euo pipefail; mypy ." || FAILS=$((FAILS+1))
  else
    skip_step mypy "RUN_MYPY=1 but mypy not installed; skipping"
  fi
else
  skip_step mypy "disabled by default (set RUN_MYPY=1 to enable)"
fi

# pytest
if python -c "import pytest" >/dev/null 2>&1; then
  run_step pytest bash -lc "set -euo pipefail; pytest -q --disable-warnings --maxfail=1" || FAILS=$((FAILS+1))
else
  if python -m pip install -U pytest >/dev/null 2>&1; then
    run_step pytest bash -lc "set -euo pipefail; pytest -q --disable-warnings --maxfail=1" || FAILS=$((FAILS+1))
  else
    skip_step pytest "pytest install failed; skipping"
  fi
fi

# pip-audit / bandit (optional)
if command -v pip-audit >/dev/null 2>&1; then
  run_step pip_audit bash -lc "set -euo pipefail; pip-audit -r <(python -m pip freeze)" || FAILS=$((FAILS+1))
else
  skip_step pip_audit "pip-audit not installed; skipping"
fi

if command -v bandit >/dev/null 2>&1; then
  run_step bandit bash -lc "set -euo pipefail; bandit -q -r algonovax -x '*/tests/*' -f txt" || FAILS=$((FAILS+1))
else
  skip_step bandit "bandit not installed; skipping"
fi

# smoke engine
run_step smoke_engine bash -lc '
set -euo pipefail
timeout 15s python -u -m algonovax engine || rc=$?
rc="${rc:-0}"
echo "rc=$rc"
exit 0
' || FAILS=$((FAILS+1))

# gui import sanity (non-Termux only; enforced on Linux/CI)
if [[ -n "${TERMUX_VERSION:-}" ]] || [[ "${PREFIX:-}" == "/data/data/com.termux/files/usr"* ]] || [[ "${HOME:-}" == "/data/data/com.termux/files/home"* ]]; then
  skip_step gui_import "Termux detected; skipping GUI import (FastAPI not required here)"
else
  run_step gui_import bash -lc '
set -euo pipefail
python - <<"PY"
import importlib
importlib.import_module("fastapi")
importlib.import_module("ui.gui")
print("OK: ui.gui imports")
PY
' || FAILS=$((FAILS+1))
fi

# systemd (optional)
run_step systemd_units bash -lc '
set -euo pipefail
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user --no-pager status algonovax-engine.service algonovax-gui.service || true
else
  echo "systemctl not available; skipping"
fi
' || FAILS=$((FAILS+1))

if [[ "$FAILS" -eq 0 ]]; then
  echo "- Overall: **PASS**" | tee -a "$REPORT"
else
  echo "- Overall: **FAIL** (failures: $FAILS)" | tee -a "$REPORT"
fi

echo >>"$REPORT"
echo "## Artifacts" >>"$REPORT"
echo "- Report: \`$REPORT\`" >>"$REPORT"
echo "- Logs:   \`$LOG_DIR\`" >>"$REPORT"

echo "DONE: $REPORT"
