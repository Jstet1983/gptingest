"""
github_to_gptingester
Configuration
Version: 0.2.0
"""

from __future__ import annotations

import os
from pathlib import Path

VERSION = "0.2.0"
APP_NAME = "github_to_gptingester"

ROOT = Path(__file__).resolve().parent

REPOS = ROOT / "repos"
LOGS = ROOT / "logs"
CACHE = ROOT / "cache"
REPORTS = ROOT / "reports"
DB = ROOT / "db"

for d in (REPOS, LOGS, CACHE, REPORTS, DB):
    d.mkdir(parents=True, exist_ok=True)

GITHUB_USER = os.getenv("GITHUB_USER", "Jstet1983")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

SQLITE_DB = DB / "ingestion.db"

LOG_FILE = LOGS / "github_to_gptingester.txt"

API_URL = "https://api.github.com"

REQUEST_TIMEOUT = 60

MAX_WORKERS = max(2, os.cpu_count() or 2)

# Embedding configuration
EMBEDDING_PROVIDER = "mock"
EMBED_BATCH_SIZE = 32
EMBED_MAX_RETRIES = 3
