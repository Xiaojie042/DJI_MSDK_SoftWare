"""Minimal pytest compatibility layer for direct script execution."""

from __future__ import annotations

import importlib.util
import math
import sys
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable


class _Approx:
    def __init__(self, expected: float, rel: float = 1e-6, abs: float = 1e-12):
        self.expected = expected
        self.rel = rel
        self.abs = abs

    def __eq__(self, actual: Any) -> bool:
        try:
            return math.isclose(float(actual), float(self.expected), rel_tol=self.rel, abs_tol=self.abs)
        except (TypeError, ValueError):
            return False

    def __repr__(self) -> str:
        return f"approx({self.expected!r}, rel={self.rel!r}, abs={self.abs!r})"


def approx(expected: float, rel: float = 1e-6, abs: float = 1e-12) -> _Approx:
    return _Approx(expected=expected, rel=rel, abs=abs)


def main(args: list[str] | None = None) -> int:
    paths = [Path(arg) for arg in (args or []) if not str(arg).startswith("-")]
    if not paths:
        main_module = sys.modules.get("__main__")
        main_file = getattr(main_module, "__file__", None)
        if main_file:
            paths = [Path(main_file)]

    total = 0
    failed = 0
    for path in paths:
        module = _load_module(path.resolve())
        for test_name, test_callable in _iter_tests(module):
            total += 1
            try:
                test_callable()
                print(f"PASS {test_name}")
            except Exception:
                failed += 1
                print(f"FAIL {test_name}")
                traceback.print_exc()

    print(f"{total - failed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def _load_module(path: Path) -> ModuleType:
    main_module = sys.modules.get("__main__")
    main_file = Path(getattr(main_module, "__file__", "")).resolve() if getattr(main_module, "__file__", None) else None
    if main_file == path:
        return main_module  # type: ignore[return-value]

    module_name = f"_compat_{path.stem}_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load test module: {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _iter_tests(module: ModuleType) -> Iterable[tuple[str, Any]]:
    module_name = getattr(module, "__name__", "test_module")

    for name in sorted(dir(module)):
        obj = getattr(module, name)
        if name.startswith("test_") and callable(obj):
            yield f"{module_name}::{name}", obj

        if name.startswith("Test") and isinstance(obj, type):
            for method_name in sorted(dir(obj)):
                if not method_name.startswith("test_"):
                    continue

                def _run_method(cls=obj, method=method_name) -> None:
                    instance = cls()
                    setup = getattr(instance, "setup_method", None)
                    if callable(setup):
                        setup()
                    getattr(instance, method)()
                    teardown = getattr(instance, "teardown_method", None)
                    if callable(teardown):
                        teardown()

                yield f"{module_name}::{name}::{method_name}", _run_method
