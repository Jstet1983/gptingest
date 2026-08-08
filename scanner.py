#!/usr/bin/env python3
"""
scanner.py
Version: 0.1.0

Repository file scanner.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

from config import REPOS, SQLITE_DB
from logger import logger

SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
}

conn = sqlite3.connect(SQLITE_DB)

conn.execute("""
CREATE TABLE IF NOT EXISTS files(
    id INTEGER PRIMARY KEY,
    repository TEXT,
    relative_path TEXT,
    sha256 TEXT,
    size INTEGER,
    modified REAL,
    UNIQUE(repository, relative_path)
)
""")

conn.commit()


def sha256sum(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)

    return h.hexdigest()


def scan_repo(repo: Path):

    logger.info("Scanning %s", repo.name)

    files = 0

    for root, dirs, filenames in os.walk(repo):

        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        root_path = Path(root)

        for filename in filenames:

            full = root_path / filename

            try:

                rel = full.relative_to(repo)

                stat = full.stat()

                digest = sha256sum(full)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO files(
                        repository,
                        relative_path,
                        sha256,
                        size,
                        modified
                    )
                    VALUES(?,?,?,?,?)
                    """,
                    (
                        repo.name,
                        str(rel),
                        digest,
                        stat.st_size,
                        stat.st_mtime,
                    ),
                )

                files += 1

            except Exception as e:
                logger.exception(e)

    conn.commit()

    logger.info(
        "%s : %d files",
        repo.name,
        files,
    )

    return files


def main():

    total = 0

    for repo in sorted(REPOS.iterdir()):

        if repo.is_dir():
            total += scan_repo(repo)

    print()
    print("==========================")
    print(f"Files indexed : {total}")
    print("==========================")


if __name__ == "__main__":
    main()
