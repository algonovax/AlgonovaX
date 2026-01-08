from __future__ import annotations
import sys
import yaml

from algonovax.engine.engine import run
from algonovax.strategy.ema_cross_mvp import EMACrossMVP

def main() -> int:
    """
    Load and validate configuration from config/config.yaml, execute the EMACrossMVP strategy, and return an exit status.
    
    The function expects the YAML file to contain a mapping with a required "pair" key. It runs the strategy runner and maps observable failures to specific exit codes.
    
    Returns:
        int: Exit status code — the value returned by the strategy runner on successful execution; 2 if the configuration file is missing; 1 for any other error.
    """
    try:
        with open("config/config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if not isinstance(cfg, dict):
            raise RuntimeError("config must be a YAML mapping")
        if "pair" not in cfg:
            raise RuntimeError("config missing 'pair'")
        return run(cfg, EMACrossMVP(fast=12, slow=26))
    except FileNotFoundError:
        print("Missing config/config.yaml", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())