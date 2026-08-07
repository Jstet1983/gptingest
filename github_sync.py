#!/usr/bin/env python3
"""
github_sync.py
Version: 0.5.0
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from config import REPOS
from database import db
from github_api import get
from logger import logger

if shutil.which("git") is None:
    raise RuntimeError("git executable not found")


def git(*args, cwd=None):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    return result


def clone_or_update(repo, dry_run=False):

    target = REPOS / repo["name"]

    if dry_run:
        action = "UPDATE" if target.exists() else "CLONE"
        print(f"{action:7} {repo['full_name']}")
        return

    if target.exists():
        logger.info("Updating %s", repo["full_name"])
        git("fetch", "--all", cwd=target)
        git("pull", cwd=target)
    else:
        logger.info("Cloning %s", repo["full_name"])
        git("clone", repo["clone_url"], str(target))


def smoke_test():
    user = get("/user")
    repos = get("/user/repos?per_page=1")

    print("GitHub authentication : OK")
    print(f"Authenticated user    : {user['login']}")
    print(f"Repository sample     : {repos[0]['full_name'] if repos else 'None'}")
    print("Smoke test passed.")
    return 0


def sync(dry_run=False, limit=None):

    conn = db()

    processed = 0
    page = 1

    while True:

        repos = get(f"/user/repos?page={page}&per_page=100")

        if not repos:
            break

        for repo in repos:

            if limit is not None and processed >= limit:
                print(f"Limit reached ({limit})")
                print(f"Repositories processed: {processed}")
                return 0

            processed += 1

            try:

                clone_or_update(repo, dry_run)

                if not dry_run:
                    conn.execute(
                        """
                        UPDATE repositories
                        SET indexed=1
                        WHERE full_name=?
                        """,
                        (repo["full_name"],),
                    )
                    conn.commit()

            except Exception:
                logger.exception(
                    "Failed processing %s",
                    repo["full_name"],
                )

        page += 1

    print(f"Repositories processed: {processed}")
    return 0


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--test",
        action="store_true",
        help="Quick GitHub connectivity test",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not clone or update",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N repositories",
    )

    args = parser.parse_args()

    if args.test:
        return smoke_test()

    return sync(
        dry_run=args.dry_run,
        limit=args.limit,
    )


if __name__ == "__main__":
    sys.exit(main())
