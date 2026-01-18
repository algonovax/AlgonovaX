# AlgoNovaX

AlgoNovaX is a modular algorithmic trading engine + GUI designed for reproducible backtesting and controlled live execution with safety gates (killswitch, logging, and deterministic runs). It supports multiple exchange adapters (paper + real exchanges) and strategy plugins.

> **Status:** Active development  
> **Primary goals:** safety, reproducibility, and clean operational UX

---

## Features

- **Engine runner** with structured logs
- **Strategy plugin system** (`algonovax/strategies/*`)
- **Paper trading mode** for safe iteration
- **Killswitch** (`data/KILL_SWITCH`) to hard-stop execution immediately
- **Backtesting** entrypoint (project-dependent)
- **GUI** (project-dependent; runs as a separate service)
- **Extensible exchange adapters** (e.g., Kraken/Coinbase/BinanceUS depending on your setup)

---

## Repo Layout (high level)

- `algonovax/` — core package
  - `engine/` — execution loop and trade lifecycle
  - `strategies/` — strategy implementations
  - `gui/` — GUI app
- `scripts/` — operational scripts (smoke tests, runners, utilities)
- `config/` — env templates and configuration examples
- `data/` — runtime flags/state (e.g., `KILL_SWITCH`)
- `logs/` — runtime logs

---

## Quick Start (local)

### 1) Clone
```bash
git clone https://github.com/<YOUR_GITHUB_USER>/AlgoNovaX.git
cd AlgoNovaX ## Hi there 👋

<!--
**algonovax/AlgonovaX** is a ✨ _special_ ✨ repository because its `README.md` (this file) appears on your GitHub profile.

