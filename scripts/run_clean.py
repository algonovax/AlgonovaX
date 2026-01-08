from __future__ import annotations
import sys
from pathlib import Path
import yaml

def main() -> int:
    """
    Run a clean trading simulation using configuration from config/config.yaml.
    
    Deletes data/state.json if present, loads and validates the YAML configuration, ensures a `paper` section with numeric `starting_cash_quote` and `stake_quote` (defaulting to 1000.0 and 100.0), constructs an EMACrossMVP strategy with the configured stake, and executes the engine run.
    
    Returns:
        exit_code (int): The integer exit code: the engine run's integer result on success, `2` if the config file is missing, or `1` for any other fatal error.
    """
    try:
        Path("data/state.json").unlink(missing_ok=True)

        with open("config/config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if not isinstance(cfg, dict):
            raise RuntimeError("config must be a mapping")

        cfg.setdefault("paper", {})
        cfg["paper"]["starting_cash_quote"] = float(cfg["paper"].get("starting_cash_quote", 1000.0))
        cfg["paper"]["stake_quote"] = float(cfg["paper"].get("stake_quote", 100.0))

        from algonovax.engine.engine import run
        from algonovax.strategy.ema_cross_mvp import EMACrossMVP

        return int(run(cfg, EMACrossMVP(stake_quote=cfg["paper"]["stake_quote"])))
    except FileNotFoundError:
        print("Missing config/config.yaml", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())