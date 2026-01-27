from __future__ import annotations

from pathlib import Path
import ast
import sys
import py_compile


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "algonovax" / "engine" / "engine.py"

print("doctor:", Path(__file__).resolve())
print("root  :", ROOT)
print("engine:", ENGINE)

if not ENGINE.exists():
    die(f"FAIL: engine file missing: {ENGINE}")

src = ENGINE.read_text("utf-8", errors="ignore").replace("\t", "    ")

try:
    tree = ast.parse(src, filename=str(ENGINE))
except Exception as e:
    die(f"FAIL: ast.parse failed: {e!r}")

top_level = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
names = [n.name for n in top_level]

def_lines = {
    n.name: (n.lineno, getattr(n, "end_lineno", None), n.col_offset) for n in top_level
}

print("top-level defs:", names)

# hard requirements
if names.count("_pick_intent") != 1:
    die(
        f"FAIL: expected exactly 1 top-level _pick_intent, got {names.count('_pick_intent')} -> {def_lines.get('_pick_intent')}"
    )
if names.count("run_loop") != 1:
    die(
        f"FAIL: expected exactly 1 top-level run_loop, got {names.count('run_loop')} -> {def_lines.get('run_loop')}"
    )

# ensure run_loop truly top-level
rl = next(n for n in top_level if n.name == "run_loop")
if rl.col_offset != 0:
    die(f"FAIL: run_loop is not top-level (col_offset={rl.col_offset})")

try:
    py_compile.compile(str(ENGINE), doraise=True)
except Exception as e:
    die(f"FAIL: engine.py does not compile: {e!r}")

print("OK: engine.py compiles and doctor checks passed")
