#!/usr/bin/env python3

from __future__ import annotations

import sqlite3

from config import SQLITE_DB

from vector_stores.base import VectorStore
from vector_stores.sqlite_store import SQLiteVectorStore


def load_vector_store(
    name: str = "sqlite",
    connection: sqlite3.Connection | None = None,
) -> VectorStore:

    name = name.lower().strip()

    if name == "sqlite":
        return SQLiteVectorStore(
            SQLITE_DB,
            connection=connection,
        )

    raise ValueError(
        f"Unknown vector store: {name}"
    )
