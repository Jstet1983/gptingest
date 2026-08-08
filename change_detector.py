#!/usr/bin/env python3
"""
change_detector.py
Version 0.1.0

Compares current scan against previous state and produces
an ingestion queue containing only changed files.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from config import SQLITE_DB
from logger import logger

conn = sqlite3.connect(SQLITE_DB)

conn.execute("""
CREATE TABLE IF NOT EXISTS previous_files(
    repository TEXT,
    relative_path TEXT,
    sha256 TEXT,
    PRIMARY KEY(repository,relative_path)
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS ingestion_queue(
    repository TEXT,
    relative_path TEXT,
    sha256 TEXT,
    status TEXT
)
""")

conn.commit()


def load(table):

    rows = conn.execute(
        f"""
        SELECT repository,
               relative_path,
               sha256
        FROM {table}
        """
    )

    return {
        (r, p): h
        for r, p, h in rows
    }


current = load("files")
previous = load("previous_files")

new_files = 0
modified = 0
deleted = 0

conn.execute("DELETE FROM ingestion_queue")

for key, sha in current.items():

    if key not in previous:

        new_files += 1

        conn.execute(
            """
            INSERT INTO ingestion_queue
            VALUES(?,?,?,'NEW')
            """,
            (*key, sha),
        )

    elif previous[key] != sha:

        modified += 1

        conn.execute(
            """
            INSERT INTO ingestion_queue
            VALUES(?,?,?,'MODIFIED')
            """,
            (*key, sha),
        )

for key in previous:

    if key not in current:

        deleted += 1

conn.execute("DELETE FROM previous_files")

conn.execute("""
INSERT INTO previous_files
SELECT repository,
       relative_path,
       sha256
FROM files
""")

conn.commit()

queued = conn.execute(
    "SELECT COUNT(*) FROM ingestion_queue"
).fetchone()[0]

print()
print("==============================")
print("Incremental Scan")
print("==============================")
print("New files      :", new_files)
print("Modified files :", modified)
print("Deleted files  :", deleted)
print("Queued         :", queued)
print("==============================")

logger.info(
    "Queue built: %s files",
    queued,
)
