#!/usr/bin/env python3
"""
chunker.py
Version 0.2.0

Builds text chunks either from:
  • ingestion_queue (default)
  • all indexed files (--full)
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from config import REPOS, SQLITE_DB
from logger import logger

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

conn = sqlite3.connect(SQLITE_DB)

conn.execute("""
CREATE TABLE IF NOT EXISTS chunks(
    repository TEXT,
    relative_path TEXT,
    chunk_index INTEGER,
    text TEXT,
    PRIMARY KEY(repository, relative_path, chunk_index)
)
""")
conn.commit()

BINARY_EXTENSIONS = {
    ".so", ".dll", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif",
    ".webp", ".ico", ".zip", ".gz",
    ".tar", ".7z", ".rar", ".pdf",
    ".db", ".sqlite", ".sqlite3",
}


def chunk_text(text: str):
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for start in range(0, len(text), step):
        yield text[start:start + CHUNK_SIZE]


def iter_files(full_mode: bool):
    if full_mode:
        sql = """
        SELECT repository, relative_path
        FROM files
        ORDER BY repository, relative_path
        """
    else:
        sql = """
        SELECT repository, relative_path
        FROM ingestion_queue
        WHERE status != 'DELETED'
        ORDER BY repository, relative_path
        """

    yield from conn.execute(sql)


def process_file(repo: str, rel: str):

    path = REPOS / repo / rel

    if not path.exists():
        return 0

    if path.suffix.lower() in BINARY_EXTENSIONS:
        return 0

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return 0

    conn.execute(
        """
        DELETE FROM chunks
        WHERE repository=?
          AND relative_path=?
        """,
        (repo, rel),
    )

    chunks = 0

    for idx, chunk in enumerate(chunk_text(text)):
        conn.execute(
            """
            INSERT INTO chunks
            VALUES(?,?,?,?)
            """,
            (repo, rel, idx, chunk),
        )
        chunks += 1

    return chunks


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Rebuild chunks for all indexed files",
    )
    args = parser.parse_args()

    total_chunks = 0
    total_files = 0

    for repo, rel in iter_files(args.full):
        total_files += 1
        total_chunks += process_file(repo, rel)

    conn.commit()

    print()
    print("===================================")
    print("Chunk Builder")
    print("===================================")
    print("Mode   :", "FULL" if args.full else "QUEUE")
    print("Files  :", total_files)
    print("Chunks :", total_chunks)
    print("===================================")

    logger.info(
        "Chunk build complete (%s): %d files, %d chunks",
        "FULL" if args.full else "QUEUE",
        total_files,
        total_chunks,
    )


if __name__ == "__main__":
    main()
