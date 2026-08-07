#!/usr/bin/env python3
"""
github_to_gptingester
Project Test Suite
Version 0.3.0
"""

from __future__ import annotations

import importlib
import shutil
import sqlite3
import subprocess
import sys

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"[PASS] {msg}")


def bad(msg, exc=""):
    global FAIL
    FAIL += 1
    print(f"[FAIL] {msg}")
    if exc:
        print(exc)


def test_import(module):
    try:
        importlib.import_module(module)
        ok(f"Import {module}")
    except Exception as e:
        bad(f"Import {module}", e)


def test_git():
    if shutil.which("git"):
        ok("Git executable")
    else:
        bad("Git executable")


def test_database():
    try:
        import config

        sqlite3.connect(config.SQLITE_DB).close()
        ok("SQLite database")
    except Exception as e:
        bad("SQLite database", e)


def test_api():
    try:
        from github_api import get

        user = get("/user")
        ok(f"GitHub API ({user['login']})")
    except Exception as e:
        bad("GitHub API", e)


def test_sync():
    try:
        result = subprocess.run(
            [sys.executable, "github_sync.py"],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            ok("github_sync.py")
        else:
            bad(
                "github_sync.py",
                result.stderr,
            )

    except Exception as e:
        bad("github_sync.py", e)


def main():

    print("=" * 60)
    print("GitHub → GPT Ingester")
    print("Self Test")
    print("=" * 60)

    for module in (
        "config",
        "logger",
        "database",
        "github_api",
    ):
        test_import(module)

    test_git()

    test_database()

    test_api()

    test_sync()

    print("=" * 60)

    print(f"Passed : {PASS}")
    print(f"Failed : {FAIL}")

    print("=" * 60)

    sys.exit(FAIL)


if __name__ == "__main__":
    main()
