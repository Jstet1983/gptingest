#!/usr/bin/env python3
"""
GitHub → GPT Ingester
Metadata Extractor
Version 0.3.0
"""

from __future__ import annotations

import argparse
import mimetypes
import sqlite3
from pathlib import Path

from config import REPOS, SQLITE_DB
from logger import logger

conn = sqlite3.connect(SQLITE_DB)

conn.execute("""
CREATE TABLE IF NOT EXISTS file_metadata(
    repository TEXT,
    relative_path TEXT,
    mime_type TEXT,
    extension TEXT,
    is_text INTEGER,
    language TEXT,
    encoding TEXT,
    line_count INTEGER,
    word_count INTEGER,
    char_count INTEGER,
    token_estimate INTEGER,
    is_sensitive INTEGER DEFAULT 0,
    PRIMARY KEY(repository, relative_path)
)
""")

try:
    conn.execute(
        "ALTER TABLE file_metadata ADD COLUMN is_sensitive INTEGER DEFAULT 0"
    )
except sqlite3.OperationalError:
    pass

LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".rs": "Rust",
    ".go": "Go",
    ".sh": "Shell",
    ".md": "Markdown",
    ".txt": "Plain Text",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".xml": "XML",
    ".html": "HTML",
    ".css": "CSS",
    ".toml": "TOML",
    ".ini": "INI",
}

SPECIAL_FILES = {
    ".gitignore": ("Plain Text", "text/plain"),
    "README": ("Markdown", "text/markdown"),
    "README.md": ("Markdown", "text/markdown"),
    "LICENSE": ("Plain Text", "text/plain"),
    "CHANGELOG": ("Plain Text", "text/plain"),
    "Dockerfile": ("Dockerfile", "text/plain"),
    "Makefile": ("Makefile", "text/plain"),
    "config": ("Plain Text", "text/plain"),
    "requirements.txt": ("Requirements", "text/plain"),
}

SENSITIVE_NAMES = {
    ".env",
    "credentials",
    "id_rsa",
    "id_ed25519",
    "openai.key",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar",
    ".so", ".dll", ".exe",
    ".db", ".sqlite", ".sqlite3",
}

def estimate_tokens(chars):
    return max(1, chars // 4)

def classify(path: Path):
    name = path.name

    if name in SPECIAL_FILES:
        lang, mime = SPECIAL_FILES[name]
        return lang, mime

    lang = LANGUAGE_MAP.get(path.suffix.lower(), "Unknown")
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"

    return lang, mime

def process(repo, rel):
    path = REPOS / repo / rel

    if not path.exists():
        return False

    lang, mime = classify(path)
    sensitive = 1 if path.name in SENSITIVE_NAMES else 0
    ext = path.suffix.lower()

    if ext in BINARY_EXTENSIONS:
        conn.execute(
            """
            INSERT OR REPLACE INTO file_metadata
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                repo,
                rel,
                mime,
                ext,
                0,
                lang,
                "",
                0,
                0,
                0,
                0,
                sensitive,
            ),
        )
        return True

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return False

    lines = text.count("\n") + 1
    words = len(text.split())
    chars = len(text)

    conn.execute(
        """
        INSERT OR REPLACE INTO file_metadata
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            repo,
            rel,
            mime,
            ext,
            1,
            lang,
            "utf-8",
            lines,
            words,
            chars,
            estimate_tokens(chars),
            sensitive,
        ),
    )

    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    if args.full:
        rows = conn.execute(
            "SELECT repository, relative_path FROM files"
        )
    else:
        rows = conn.execute(
            """
            SELECT repository, relative_path
            FROM ingestion_queue
            WHERE status!='DELETED'
            """
        )

    total = 0

    for repo, rel in rows:
        if process(repo, rel):
            total += 1

    conn.commit()

    print()
    print("===================================")
    print("Metadata Extractor v0.3.0")
    print("===================================")
    print("Files processed :", total)
    print("===================================")

    logger.info(
        "Metadata updated: %d files",
        total,
    )

if __name__ == "__main__":
    main()
