#!/usr/bin/env bash
# Overwrite .gitignore with canonical content (no merge/dedupe).
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

on_err() {
  local ec=$?
  echo "FIX_GITIGNORE_CRASH exit_code=$ec line=${BASH_LINENO[0]} cmd=${BASH_COMMAND}" >&2
  exit "$ec"
}
trap on_err ERR

TMP=".gitignore.__tmp__.$$"
trap 'rm -f "$TMP"' EXIT

cat > "$TMP" <<'GITIGNORE'
# ===== Python =====
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.so
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml

# Virtual envs
.venv/
venv/
.env/
.env.*
!.env.example

# ===== Logs / runtime =====
logs/
*.log

# ===== Data / outputs =====
data/
*.csv
*.jsonl
*.parquet

# ===== Secrets =====
config/secrets.env
paper_wallet.json

# ===== Backups / temp =====
*.bak
*.bak.*
*~
*.tmp
*.swp
scripts/_bak/
_quarantine/

# ===== OS / editor =====
.DS_Store
.idea/
.vscode/

# ===== Node =====
node_modules/
GITIGNORE

# Sanity check
tail -n 1 "$TMP" | grep -qxF "node_modules/" || { echo "BAD_WRITE" >&2; exit 2; }

mv -f "$TMP" .gitignore
echo "OK: wrote canonical .gitignore"
