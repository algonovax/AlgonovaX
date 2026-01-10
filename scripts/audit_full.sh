#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ts="$(date +%Y%m%d_%H%M%S)"
OUT="audit/audit.$ts.txt"
JSON="audit/audit.$ts.json"

mkdir -p audit logs

log() { echo "[$(date -Is)] $*" | tee -a "$OUT" >&2; }
section() { echo -e "\n=== $* ===" | tee -a "$OUT" >&2; }

trap 'rc=$?; log "EXIT rc=$rc out=$OUT json=$JSON"; exit $rc' EXIT

section "ENV"
{
  echo "root=$ROOT"
  echo "uname=$(uname -a || true)"
  echo "whoami=$(whoami || true)"
  echo "pwd=$(pwd)"
  echo "git=$(git rev-parse --short HEAD 2>/dev/null || echo no-git)"
  echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo no-git)"
  echo "python=$(python -V 2>&1 || true)"
  echo "pip=$(pip -V 2>&1 || true)"
} | tee -a "$OUT" >/dev/null

section "GIT STATUS"
git status --porcelain=v1 2>/dev/null | tee -a "$OUT" >/dev/null || true

section "SECRETS / KEY HYGIENE (BEST-EFFORT)"
# Greps for common key patterns. This is NOT perfect; it's a tripwire.
rg -n --hidden --no-ignore-vcs -S \
  '(API[_-]?KEY|SECRET|TOKEN|PASSPHRASE|PRIVATE[_-]?KEY|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY|coinbase|kraken).{0,40}=' \
  . 2>/dev/null | tee -a "$OUT" >/dev/null || true

# Show env files tracked by git (should be NONE)
git ls-files | rg -n '\.(env|pem|key|p12|pfx)$' | tee -a "$OUT" >/dev/null || true

section "DEPENDENCY AUDIT"
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit -r requirements.txt 2>&1 | tee -a "$OUT" >/dev/null || true
else
  log "pip-audit not installed; installing into current venv"
  python -m pip install -q --upgrade pip pip-audit || true
  pip-audit -r requirements.txt 2>&1 | tee -a "$OUT" >/dev/null || true
fi

section "STATIC QUALITY GATES"
if command -v ruff >/dev/null 2>&1; then
  ruff check . 2>&1 | tee -a "$OUT" >/dev/null || true
else
  python -m pip install -q ruff || true
  ruff check . 2>&1 | tee -a "$OUT" >/dev/null || true
fi

if command -v mypy >/dev/null 2>&1; then
  mypy algonovax 2>&1 | tee -a "$OUT" >/dev/null || true
else
  python -m pip install -q mypy || true
  mypy algonovax 2>&1 | tee -a "$OUT" >/dev/null || true
fi

section "SECURITY STATIC (BANDIT)"
if command -v bandit >/dev/null 2>&1; then
  bandit -q -r algonovax scripts exchanges 2>&1 | tee -a "$OUT" >/dev/null || true
else
  python -m pip install -q bandit || true
  bandit -q -r algonovax scripts exchanges 2>&1 | tee -a "$OUT" >/dev/null || true
fi

section "TESTS"
if command -v pytest >/dev/null 2>&1; then
  pytest -q 2>&1 | tee -a "$OUT" >/dev/null || true
else
  python -m pip install -q pytest || true
  pytest -q 2>&1 | tee -a "$OUT" >/dev/null || true
fi

section "RUNTIME RELIABILITY TRIPWIRES"
# Crash-loop culprits: duplicate runners, orphan locks, KILL_SWITCH, etc.
ls -la data 2>/dev/null | tee -a "$OUT" >/dev/null || true
test -f data/engine.lock && { echo "FOUND data/engine.lock" | tee -a "$OUT" >/dev/null; } || true
test -f data/KILL_SWITCH && { echo "FOUND data/KILL_SWITCH" | tee -a "$OUT" >/dev/null; } || true

# systemd (if present)
if command -v systemctl >/dev/null 2>&1; then
  section "SYSTEMD USER SERVICES (ALGONOVAX)"
  systemctl --user --no-pager --full status algonovax-engine.service 2>&1 | tee -a "$OUT" >/dev/null || true
  systemctl --user --no-pager --full status algonovax-gui.service 2>&1 | tee -a "$OUT" >/dev/null || true
  systemctl --user --no-pager --full status algonovax-killswitch.service 2>&1 | tee -a "$OUT" >/dev/null || true

  section "JOURNAL LAST 200 LINES (ENGINE)"
  journalctl --user -u algonovax-engine.service -n 200 --no-pager 2>&1 | tee -a "$OUT" >/dev/null || true
fi

section "TRADING SAFETY INVARIANTS (CODE SEARCH)"
# You MUST have these. If these searches return nothing, you're gambling.
rg -n --hidden --no-ignore-vcs -S \
  '(max(_|-)?loss|max(_|-)?drawdown|max(_|-)?position|max(_|-)?exposure|max(_|-)?orders|max(_|-)?daily|max(_|-)?risk|kill(_|-)?switch|slippage|fee_rate|idempotent|client_order_id|nonce|rate[_-]?limit|retry|backoff)' \
  algonovax scripts exchanges config 2>/dev/null | tee -a "$OUT" >/dev/null || true

section "WRITE SUMMARY JSON"
python - <<'PY' "$OUT" "$JSON"
from __future__ import annotations
import json
import sys
from pathlib import Path

def main() -> int:
    try:
        out_path = Path(sys.argv[1])
        json_path = Path(sys.argv[2])
        text = out_path.read_text("utf-8", errors="replace")

        def has(p: str) -> bool:
            return p in text

        summary = {
            "out": str(out_path),
            "secrets_tripwire_hit": any(k in text for k in ["BEGIN RSA PRIVATE KEY", "API_KEY", "SECRET", "TOKEN"]),
            "pip_audit_ran": "pip-audit" in text,
            "ruff_ran": "ruff" in text,
            "mypy_ran": "mypy" in text,
            "bandit_ran": "bandit" in text,
            "pytest_ran": "pytest" in text,
            "engine_lock_present": has("FOUND data/engine.lock"),
            "kill_switch_present": has("FOUND data/KILL_SWITCH"),
        }

        json_path.write_text(json.dumps(summary, indent=2), "utf-8")
        print(json.dumps(summary, indent=2))
        return 0
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
PY | tee -a "$OUT" >/dev/null

log "DONE. Paste this file back: $OUT"
