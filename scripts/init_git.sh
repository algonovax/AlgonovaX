#!/usr/bin/env bash
set -euo pipefail
cd "${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"

if [ -d .git ]; then
  echo "[OK] .git already exists"
else
  git init
fi

# Minimal, correct .gitignore (protect secrets + junk)
cat > .gitignore <<'GIT'
# Python
__pycache__/
*.py[cod]
*.pyd
*.pyo
*.pdb
*.egg-info/
.dist/
.build/
.eggs/
.venv/
venv/
.env
.env.*
!.env.example

# Logs / runtime
logs/
*.log

# Data / secrets
paper_wallet.json
data/
*.csv

# OS / editor
.DS_Store
.idea/
.vscode/

# Node
node_modules/
GIT

# Ensure placeholder files exist so dirs can be committed
mkdir -p logs data scripts systemd tests algonovax
touch logs/.gitkeep data/.gitkeep

git add -A
git commit -m "chore: initialize repository" || true

echo
git status -sb
