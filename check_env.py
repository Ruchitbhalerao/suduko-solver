#!/usr/bin/env python3
"""Environment verification for the AI-Based Sudoku Solver project.

This script is read-only: it inspects the current interpreter and reports
problems. It never installs packages and never changes system settings.

It checks:
    1. The Python version is new enough (3.10 or newer).
    2. A virtual environment is currently active.
    3. Django is importable and reports its version.

Usage:
    python check_env.py        # or: python3 check_env.py  /  py -3 check_env.py

Exit codes:
    0  all checks passed
    1  at least one check failed
"""

from __future__ import annotations

import sys

MIN_PYTHON = (3, 10)
EXPECTED_DJANGO_MAJOR_MINOR = (5, 2)


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def check_python_version() -> bool:
    current = sys.version_info
    ok = current[:2] >= MIN_PYTHON
    expected = ".".join(str(part) for part in MIN_PYTHON)
    actual = ".".join(str(part) for part in current[:3])
    print(f"[{_status(ok)}] Python version: {actual} (requires >= {expected})")
    if not ok:
        print("       Install a newer Python 3 and recreate the virtual environment.")
    return ok


def check_virtualenv() -> bool:
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    print(f"[{_status(in_venv)}] Virtual environment active: {sys.prefix}")
    if not in_venv:
        print("       Activate the project virtual environment first (see README.md).")
    return in_venv


def check_django() -> bool:
    try:
        import django
    except ImportError:
        print("[FAIL] Django is not importable in this interpreter.")
        print("       Install dependencies with: python -m pip install -r requirements.txt")
        return False

    version = django.get_version()
    expected = ".".join(str(part) for part in EXPECTED_DJANGO_MAJOR_MINOR)
    ok = version.startswith(expected)
    note = "" if ok else f" (requirements.txt pins {expected}.x)"
    print(f"[{_status(ok)}] Django {version}{note}")
    return True


def main() -> int:
    print("AI-Based Sudoku Solver - environment check")
    print("-" * 44)

    results = [
        check_python_version(),
        check_virtualenv(),
        check_django(),
    ]

    print("-" * 44)
    if all(results):
        print("All checks passed. You can run: python manage.py runserver")
        return 0

    print("Some checks failed. Resolve the items above, then re-run this script.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
