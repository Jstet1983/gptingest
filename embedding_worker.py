#!/usr/bin/env python3
"""
GitHub → GPT Ingester
Embedding Worker
Version 0.2.0

Resume-safe, retry-aware embedding worker.
"""

from __future__ import annotations

import argparse
import sqlite3
import signal
import time

from config import (
    EMBED_BATCH_SIZE,
    EMBED_MAX_RETRIES,
    EMBEDDING_PROVIDER,
    SQLITE_DB,
)
from embedding_provider import load_provider
from vector_store import load_vector_store
from logger import logger
from time_utils import utc_iso


SHUTDOWN_REQUESTED = False


def request_shutdown(signum, frame):
    global SHUTDOWN_REQUESTED
    SHUTDOWN_REQUESTED = True

    print(
        "\nShutdown requested. "
        "Finishing the current batch..."
    )




def create_run_table(conn):

    conn.execute("""
    CREATE TABLE IF NOT EXISTS embedding_runs(
        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        batch_size INTEGER NOT NULL,
        requested_limit INTEGER NOT NULL,
        continuous INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        processed INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0,
        failed INTEGER DEFAULT 0,
        duration_seconds REAL DEFAULT 0,
        throughput REAL DEFAULT 0,
        final_pending INTEGER DEFAULT 0,
        final_done INTEGER DEFAULT 0,
        final_failed INTEGER DEFAULT 0
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS worker_checkpoints(
        checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        created_at TEXT NOT NULL,
        batches INTEGER NOT NULL,
        processed INTEGER NOT NULL,
        completed INTEGER NOT NULL,
        failed INTEGER NOT NULL,
        pending INTEGER NOT NULL,
        done INTEGER NOT NULL,
        failed_queue INTEGER NOT NULL,
        throughput REAL NOT NULL
    )
    """)

    conn.commit()


def write_checkpoint(
    conn,
    run_id,
    batches,
    processed,
    completed,
    failed,
    throughput,
):
    stats = queue_stats(conn)

    conn.execute(
        """
        INSERT INTO worker_checkpoints(
            run_id,
            created_at,
            batches,
            processed,
            completed,
            failed,
            pending,
            done,
            failed_queue,
            throughput
        )
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            utc_iso(),
            batches,
            processed,
            completed,
            failed,
            stats.get("PENDING", 0),
            stats.get("DONE", 0),
            stats.get("FAILED", 0),
            throughput,
        ),
    )

    conn.commit()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Embedding queue worker"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=EMBED_BATCH_SIZE,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum total chunks to process; 0 = one batch",
    )

    parser.add_argument(
        "--provider",
        default=EMBEDDING_PROVIDER,
    )

    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry FAILED records below retry limit",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show embedding queue statistics and exit",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show detailed worker status and exit",
    )

    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Process batches until the queue is empty",
    )

    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Maximum batches in continuous mode; 0 = unlimited",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pending work without processing it",
    )

    parser.add_argument(
        "--max-seconds",
        type=float,
        default=0,
        help="Maximum worker runtime; 0 = unlimited",
    )

    return parser.parse_args()


def recover_stale_processing(conn):
    cur = conn.execute("""
        UPDATE embedding_queue
        SET status='PENDING'
        WHERE status='PROCESSING'
    """)

    conn.commit()

    return cur.rowcount


def reset_retryable_failures(conn):
    cur = conn.execute(
        """
        UPDATE embedding_queue
        SET status='PENDING'
        WHERE status='FAILED'
          AND retries < ?
        """,
        (EMBED_MAX_RETRIES,),
    )

    conn.commit()

    return cur.rowcount



def process_batch_isolated(
    conn,
    provider,
    store,
    rows,
):
    """
    Embed a batch. If the provider rejects the batch,
    recursively split it until failures are isolated.
    """

    if not rows:
        return 0, 0

    texts = [row[3] for row in rows]

    try:
        vectors = provider.embed_batch(texts)

        if len(vectors) != len(rows):
            raise RuntimeError(
                f"Provider returned {len(vectors)} "
                f"vectors for {len(rows)} chunks"
            )

        completed = 0

        for row, vector in zip(rows, vectors):

            repo, rel, chunk_index, _ = row

            store.add(
                repository=repo,
                relative_path=rel,
                chunk_index=chunk_index,
                vector=vector,
                model=provider.model,
            )

            conn.execute(
                """
                UPDATE embedding_queue
                SET status='DONE'
                WHERE repository=?
                  AND relative_path=?
                  AND chunk_index=?
                """,
                (repo, rel, chunk_index),
            )

            completed += 1

        conn.commit()

        return completed, 0

    except Exception as exc:

        conn.rollback()

        if len(rows) == 1:

            repo, rel, chunk_index, _ = rows[0]

            logger.error(
                "Isolated embedding failure: "
                "%s / %s [%s]: %s",
                repo,
                rel,
                chunk_index,
                exc,
            )

            conn.execute(
                """
                UPDATE embedding_queue
                SET status='FAILED',
                    retries=retries+1
                WHERE repository=?
                  AND relative_path=?
                  AND chunk_index=?
                """,
                (repo, rel, chunk_index),
            )

            conn.commit()

            return 0, 1

        midpoint = len(rows) // 2

        left = rows[:midpoint]
        right = rows[midpoint:]

        logger.warning(
            "Batch of %d failed; splitting %d + %d",
            len(rows),
            len(left),
            len(right),
        )

        left_done, left_failed = process_batch_isolated(
            conn,
            provider,
            store,
            left,
        )

        right_done, right_failed = process_batch_isolated(
            conn,
            provider,
            store,
            right,
        )

        return (
            left_done + right_done,
            left_failed + right_failed,
        )



def process_batch(conn, provider, store, batch_size):

    rows = conn.execute(
        """
        SELECT
            q.repository,
            q.relative_path,
            q.chunk_index,
            c.text
        FROM embedding_queue q
        JOIN chunks c
          ON q.repository=c.repository
         AND q.relative_path=c.relative_path
         AND q.chunk_index=c.chunk_index
        WHERE q.status='PENDING'
          AND q.retries < ?
        ORDER BY q.repository,
                 q.relative_path,
                 q.chunk_index
        LIMIT ?
        """,
        (
            EMBED_MAX_RETRIES,
            batch_size,
        ),
    ).fetchall()

    if not rows:
        return 0, 0

    completed = 0
    failed = 0

    try:
        for repo, rel, chunk_index, _ in rows:
            conn.execute(
                """
                UPDATE embedding_queue
                SET status='PROCESSING'
                WHERE repository=?
                  AND relative_path=?
                  AND chunk_index=?
                """,
                (repo, rel, chunk_index),
            )

        conn.commit()

        texts = [
            text
            for _, _, _, text in rows
        ]

        vectors = provider.embed_batch(texts)

        if len(vectors) != len(rows):
            raise RuntimeError(
                f"Provider returned {len(vectors)} "
                f"vectors for {len(rows)} chunks"
            )

        for row, vector in zip(rows, vectors):

            repo, rel, chunk_index, _ = row

            store.add(
                repository=repo,
                relative_path=rel,
                chunk_index=chunk_index,
                vector=vector,
                model=provider.model,
            )

            conn.execute(
                """
                UPDATE embedding_queue
                SET status='DONE'
                WHERE repository=?
                  AND relative_path=?
                  AND chunk_index=?
                """,
                (repo, rel, chunk_index),
            )

            completed += 1

        conn.commit()

    except Exception as exc:

        conn.rollback()

        logger.exception(
            "Batch embedding failed: %s",
            exc,
        )

        for repo, rel, chunk_index, _ in rows:

            conn.execute(
                """
                UPDATE embedding_queue
                SET status='FAILED',
                    retries=retries+1
                WHERE repository=?
                  AND relative_path=?
                  AND chunk_index=?
                """,
                (repo, rel, chunk_index),
            )

            failed += 1

        conn.commit()

    return completed, failed


def queue_stats(conn):

    return dict(
        conn.execute("""
            SELECT status, COUNT(*)
            FROM embedding_queue
            GROUP BY status
        """).fetchall()
    )


def start_run(
    conn,
    provider,
    batch_size,
    requested_limit,
    continuous,
):
    started_at = utc_iso()

    cur = conn.execute(
        """
        INSERT INTO embedding_runs(
            provider,
            model,
            batch_size,
            requested_limit,
            continuous,
            started_at
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            provider.name,
            provider.model,
            batch_size,
            requested_limit,
            int(continuous),
            started_at,
        ),
    )

    conn.commit()

    return cur.lastrowid, started_at


def finish_run(
    conn,
    run_id,
    started_at,
    processed,
    completed,
    failed,
):
    finished_at = utc_iso()

    started_epoch = __import__(
        "datetime"
    ).datetime.fromisoformat(
        started_at.replace("Z", "+00:00")
    )

    finished_epoch = __import__(
        "datetime"
    ).datetime.fromisoformat(
        finished_at.replace("Z", "+00:00")
    )

    duration = (
        finished_epoch - started_epoch
    ).total_seconds()

    throughput = (
        processed / duration
        if duration > 0
        else 0
    )

    stats = queue_stats(conn)

    conn.execute(
        """
        UPDATE embedding_runs
        SET
            finished_at=?,
            processed=?,
            completed=?,
            failed=?,
            duration_seconds=?,
            throughput=?,
            final_pending=?,
            final_done=?,
            final_failed=?
        WHERE run_id=?
        """,
        (
            finished_at,
            processed,
            completed,
            failed,
            duration,
            throughput,
            stats.get("PENDING", 0),
            stats.get("DONE", 0),
            stats.get("FAILED", 0),
            run_id,
        ),
    )

    conn.commit()


def show_status(conn, store):

    stats = queue_stats(conn)

    total = sum(stats.values())
    done = stats.get("DONE", 0)
    pending = stats.get("PENDING", 0)
    processing = stats.get("PROCESSING", 0)
    failed = stats.get("FAILED", 0)

    percent = (
        (done / total) * 100
        if total
        else 0
    )

    print()
    print("===================================")
    print("Embedding Worker Status")
    print("===================================")
    print(f"Total queue   : {total}")
    print(f"Done          : {done}")
    print(f"Pending       : {pending}")
    print(f"Processing    : {processing}")
    print(f"Failed        : {failed}")
    print(f"Stored        : {store.count()}")
    print(f"Completion    : {percent:.4f}%")
    print("===================================")


def main():

    global SHUTDOWN_REQUESTED

    signal.signal(
        signal.SIGINT,
        request_shutdown,
    )

    signal.signal(
        signal.SIGTERM,
        request_shutdown,
    )

    args = parse_args()

    if args.batch_size < 1:
        raise SystemExit(
            "--batch-size must be >= 1"
        )

    if args.limit < 0:
        raise SystemExit(
            "--limit must be >= 0"
        )

    conn = sqlite3.connect(SQLITE_DB)

    conn.execute(
        "PRAGMA busy_timeout=30000"
    )

    create_run_table(conn)

    if args.stats:
        stats = queue_stats(conn)

        print()
        print("===================================")
        print("Embedding Worker Statistics")
        print("===================================")

        total = 0

        for status in sorted(stats):
            count = stats[status]
            print(f"{status:12} {count}")
            total += count

        print("-----------------------------------")
        print("Total:", total)
        print("===================================")
        return

    provider = load_provider(args.provider)
    store = load_vector_store(
        "sqlite",
        connection=conn,
    )

    if args.status:
        show_status(conn, store)
        store.close()
        return

    if args.dry_run:

        stats = queue_stats(conn)

        print()
        print("===================================")
        print("Embedding Worker Dry Run")
        print("===================================")
        print(f"Provider      : {provider.name}")
        print(f"Model         : {provider.model}")
        print(f"Batch size    : {args.batch_size}")
        print(f"Limit         : {args.limit or 'unlimited'}")
        print(f"Continuous    : {args.continuous}")
        print(f"Max batches   : {args.max_batches or 'unlimited'}")
        print("-----------------------------------")
        print(f"Pending       : {stats.get('PENDING', 0)}")
        print(f"Done          : {stats.get('DONE', 0)}")
        print(f"Failed        : {stats.get('FAILED', 0)}")
        print("===================================")

        store.close()
        return

    run_id, started_at = start_run(
        conn,
        provider,
        args.batch_size,
        args.limit,
        args.continuous,
    )

    recovered = recover_stale_processing(conn)

    retried = 0

    if args.retry_failed:
        retried = reset_retryable_failures(conn)

    if args.continuous:
        remaining = args.limit or float("inf")
    else:
        remaining = args.limit or args.batch_size

    total_done = 0
    total_failed = 0
    batches_run = 0

    started = time.monotonic()

    while remaining > 0:

        if (
            args.max_seconds > 0
            and (time.monotonic() - started)
                >= args.max_seconds
        ):
            logger.info(
                "Maximum runtime reached."
            )
            break

        if SHUTDOWN_REQUESTED:
            logger.info(
                "Graceful shutdown before next batch."
            )
            break

        if (
            args.max_batches > 0
            and batches_run >= args.max_batches
        ):
            break

        if remaining == float("inf"):
            batch = args.batch_size
        else:
            batch = min(
                args.batch_size,
                int(remaining),
            )

        done, failed = process_batch(
            conn,
            provider,
            store,
            batch,
        )

        batches_run += 1

        total_done += done
        total_failed += failed

        elapsed = time.monotonic() - started

        rate = (
            (total_done + total_failed) / elapsed
            if elapsed > 0
            else 0
        )

        print(
            f"Checkpoint: "
            f"batch={batches_run} "
            f"done={total_done} "
            f"failed={total_failed} "
            f"rate={rate:.2f}/sec"
        )

        write_checkpoint(
            conn,
            run_id,
            batches_run,
            total_done + total_failed,
            total_done,
            total_failed,
            rate,
        )

        processed = done + failed

        if processed == 0:
            break

        if remaining != float("inf"):
            remaining -= processed

        elapsed = time.monotonic() - started

        rate = (
            (total_done + total_failed) / elapsed
            if elapsed > 0
            else 0
        )


    elapsed = time.monotonic() - started

    stats = queue_stats(conn)

    print()
    print()
    print("===================================")
    print("Embedding Worker v0.2.0")
    print("===================================")
    print("Provider       :", provider.name)
    print("Model          :", provider.model)
    print("Recovered      :", recovered)
    print("Retry reset    :", retried)
    print("Processed      :", total_done + total_failed)
    print("Done           :", total_done)
    print("Failed         :", total_failed)
    print("Elapsed        :", f"{elapsed:.2f}s")
    print()
    print("Queue status:")
    for status in sorted(stats):
        print(
            f"  {status:12} {stats[status]}"
        )
    print("===================================")

    finish_run(
        conn,
        run_id,
        started_at,
        total_done + total_failed,
        total_done,
        total_failed,
    )

    logger.info(
        "Worker complete: run=%d done=%d failed=%d embeddings=%d",
        run_id,
        total_done,
        total_failed,
        store.count(),
    )

    store.close()


if __name__ == "__main__":
    main()
