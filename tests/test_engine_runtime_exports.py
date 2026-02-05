def test_runtime_exports_exist():
    from algonovax.engine import runtime
    assert hasattr(runtime, "run_loop"), "runtime.run_loop missing"
    assert hasattr(runtime, "run_once"), "runtime.run_once missing"
