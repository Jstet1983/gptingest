#!/usr/bin/env python3
"""
===========================================================
GitHub → GPT Ingester
Embedding Queue Builder
Version 0.3.0
===========================================================
"""

from __future__ import annotations

import argparse
import sqlite3

from config import SQLITE_DB
from logger import logger
from time_utils import utc_iso


def create_tables(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS embedding_queue(
        repository TEXT,
        relative_path TEXT,
        chunk_index INTEGER,
        status TEXT,
        retries INTEGER DEFAULT 0,
        created_at TEXT,
        PRIMARY KEY(
            repository,
            relative_path,
            chunk_index
        )
    )
    """)
    conn.commit()


def parse_args():
    parser = argparse.ArgumentParser(
        description="GitHub → GPT Ingester Embedding Queue"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Display queue statistics"
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the embedding queue"
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Rebuild queue from all chunks"
    )

    return parser.parse_args()


def show_stats(conn):
    print()
    print("===================================")
    print("Embedding Queue Statistics")
    print("===================================")

    rows = conn.execute("""
        SELECT status,
               COUNT(*)
        FROM embedding_queue
        GROUP BY status
        ORDER BY status
    """)

    total = 0

    for status, count in rows:
        print(f"{status:12} {count}")
        total += count

    print("-----------------------------------")
    print("Total:", total)
    print("===================================")


def reset_queue(conn):
    conn.execute("DELETE FROM embedding_queue")
    conn.commit()
    print("Embedding queue cleared.")

def build_queue(conn, full_mode=False):

    if full_mode:
        sql = """
        SELECT
            c.repository,
            c.relative_path,
            c.chunk_index
        FROM chunks c
        JOIN file_metadata m
          ON c.repository=m.repository
         AND c.relative_path=m.relative_path
        WHERE
            m.is_text=1
        AND m.is_sensitive=0
        """
    else:
        sql = """
        SELECT
            c.repository,
            c.relative_path,
            c.chunk_index
        FROM chunks c
        JOIN ingestion_queue q
          ON c.repository=q.repository
         AND c.relative_path=q.relative_path
        JOIN file_metadata m
          ON c.repository=m.repository
         AND c.relative_path=m.relative_path
        WHERE
            q.status!='DELETED'
        AND m.is_text=1
        AND m.is_sensitive=0
        """

    queued = 0

    for repo, rel, chunk in conn.execute(sql):

        cur = conn.execute(
            """
            INSERT OR IGNORE INTO embedding_queue(
                repository,
                relative_path,
                chunk_index,
                status,
                retries,
                created_at
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                repo,
                rel,
                chunk,
                "PENDING",
                0,
                utc_iso(),
            ),
        )

        if cur.rowcount > 0:
            queued += 1

    conn.commit()

    return queued


def main():

    args = parse_args()

    conn = sqlite3.connect(SQLITE_DB)

    create_tables(conn)

    if args.reset:
        reset_queue(conn)
        return

    if args.stats:
        show_stats(conn)
        return

    queued = build_queue(
        conn,
        full_mode=args.full,
    )

    print()
    print("===================================")
    print("Embedding Queue Builder")
    print("===================================")
    print("Mode   :", "FULL" if args.full else "QUEUE")
    print("Queued :", queued)
    print("===================================")

    logger.info(
        "Embedding queue updated (%d new items)",
        queued,
    )


if __name__ == "__main__":
    main()
