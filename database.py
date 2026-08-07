import sqlite3

from config import SQLITE_DB

conn = sqlite3.connect(SQLITE_DB)

conn.execute("""
CREATE TABLE IF NOT EXISTS repositories(

    id INTEGER PRIMARY KEY,

    full_name TEXT UNIQUE,

    default_branch TEXT,

    visibility TEXT,

    last_push TEXT,

    size INTEGER,

    indexed INTEGER DEFAULT 0
);
""")

conn.commit()


def db():
    return conn
