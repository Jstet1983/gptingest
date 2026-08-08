#!/usr/bin/env python3

from __future__ import annotations

import math
import sqlite3

from time_utils import utc_iso
from .base import VectorStore


class SQLiteVectorStore(VectorStore):

    name = "sqlite"

    def __init__(
        self,
        database: str,
        connection: sqlite3.Connection | None = None,
    ):
        self.database = database
        self.conn = connection or sqlite3.connect(
            database,
            timeout=30,
        )
        self._owns_connection = connection is None

        self.conn.execute(
            "PRAGMA busy_timeout=30000"
        )

        self.conn.execute(
            "PRAGMA journal_mode=WAL"
        )

        self._create_table()

    def _create_table(self):

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS embeddings(
            repository TEXT,
            relative_path TEXT,
            chunk_index INTEGER,
            model TEXT,
            dimensions INTEGER,
            embedding TEXT,
            created_at TEXT,
            PRIMARY KEY(
                repository,
                relative_path,
                chunk_index
            )
        )
        """)

        self.conn.commit()

    def add(
        self,
        repository: str,
        relative_path: str,
        chunk_index: int,
        vector: list[float],
        model: str,
    ) -> None:

        self.conn.execute(
            """
            INSERT OR REPLACE INTO embeddings(
                repository,
                relative_path,
                chunk_index,
                model,
                dimensions,
                embedding,
                created_at
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                repository,
                relative_path,
                chunk_index,
                model,
                len(vector),
                ",".join(str(x) for x in vector),
                utc_iso(),
            ),
        )

    def count(self) -> int:

        return self.conn.execute(
            "SELECT COUNT(*) FROM embeddings"
        ).fetchone()[0]

    def search(
        self,
        vector: list[float],
        limit: int = 10,
    ) -> list[dict]:

        if limit < 1:
            return []

        query_norm = math.sqrt(
            sum(x * x for x in vector)
        )

        if query_norm == 0:
            return []

        results = []

        rows = self.conn.execute("""
            SELECT
                e.repository,
                e.relative_path,
                e.chunk_index,
                e.model,
                e.dimensions,
                e.embedding,
                c.text,
                m.mime_type,
                m.extension,
                m.language,
                m.line_count,
                m.word_count,
                m.char_count,
                m.token_estimate
            FROM embeddings e
            LEFT JOIN chunks c
              ON e.repository=c.repository
             AND e.relative_path=c.relative_path
             AND e.chunk_index=c.chunk_index
            LEFT JOIN file_metadata m
              ON e.repository=m.repository
             AND e.relative_path=m.relative_path
        """)

        for row in rows:

            (
                repository,
                relative_path,
                chunk_index,
                model,
                dimensions,
                encoded,
                text,
                mime_type,
                extension,
                language,
                line_count,
                word_count,
                char_count,
                token_estimate,
            ) = row

            try:
                stored = [
                    float(x)
                    for x in encoded.split(",")
                ]
            except (ValueError, AttributeError):
                continue

            if len(stored) != len(vector):
                continue

            stored_norm = math.sqrt(
                sum(x * x for x in stored)
            )

            if stored_norm == 0:
                continue

            score = sum(
                a * b
                for a, b in zip(vector, stored)
            ) / (query_norm * stored_norm)

            results.append({
                "repository": repository,
                "relative_path": relative_path,
                "chunk_index": chunk_index,
                "score": score,
                "model": model,
                "dimensions": dimensions,
                "text": text or "",
                "mime_type": mime_type,
                "extension": extension,
                "language": language,
                "line_count": line_count,
                "word_count": word_count,
                "char_count": char_count,
                "token_estimate": token_estimate,
            })

        results.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return results[:limit]

    def close(self):

        if self._owns_connection:
            self.conn.close()
