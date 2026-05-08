"""Run backend tests from either the repository root or the backend folder."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = TEST_DIR.parent


def _default_pytest_args() -> list[str]:
    return [str(TEST_DIR), "-q"]


def _expand_direct_targets(args: list[str]) -> list[Path]:
    if not args:
        return sorted(TEST_DIR.glob("test_*.py"))

    targets: list[Path] = []
    for raw_arg in args:
        if raw_arg.startswith("-"):
            continue
        path = Path(raw_arg)
        if not path.is_absolute():
            cwd_candidate = Path.cwd() / path
            backend_candidate = BACKEND_ROOT / path
            path = cwd_candidate if cwd_candidate.exists() else backend_candidate
        if path.is_dir():
            targets.extend(sorted(path.glob("test_*.py")))
        elif path.exists():
            targets.append(path)
    return targets


def _run_without_pytest(args: list[str]) -> int:
    targets = _expand_direct_targets(args)
    if not targets:
        print("No test files found.")
        return 1

    failures = 0
    for path in targets:
        print(f"\n=== {path.relative_to(BACKEND_ROOT)} ===")
        result = subprocess.run([sys.executable, str(path)], cwd=BACKEND_ROOT)
        if result.returncode:
            failures += 1

    if failures:
        print(f"\n{failures} test file(s) failed.")
        return 1
    print(f"\n{len(targets)} test file(s) passed.")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))

    try:
        import pytest
    except ModuleNotFoundError:
        return _run_without_pytest(args)

    return int(pytest.main(args or _default_pytest_args()))


if __name__ == "__main__":
    raise SystemExit(main())
