# AlgoNovaX

![CI](https://github.com/algonovax/AlgonovaX/actions/workflows/ci.yml/badge.svg)

Trading engine + API.

## Dev
- `python -m venv .venv && source .venv/bin/activate`
- `python -m pip install -U pip setuptools wheel`
- `python -m pip install -e .`

## Run
- Start: `./scripts/engine_run.sh`
- Stop: `touch data/KILL_SWITCH`
- Logs: `tail -f logs/engine.run.log`
