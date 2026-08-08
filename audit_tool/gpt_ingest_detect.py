#!/usr/bin/env python3
"""Locate GPT ingest candidates."""

from __future__ import annotations

from audit_tool.core import append_log, build_parser, config_from_args, connect_db, export_query


def run() -> int:
    parser = build_parser("Locate GPT ingest, entity, and timeline candidate files.")
    args = parser.parse_args()
    config = config_from_args(args)
    append_log(config.audit_root, "gpt_ingest_detect_start", command="gpt_ingest_detect.py", status="START")
    out = config.audit_root / "05_gpt_ingest"
    fields = ["path", "name", "extension", "size", "modified", "category", "likely_purpose"]
    with connect_db(config.db_path) as conn:
        export_query(conn, out / "gpt_ingest_candidates.csv", "SELECT path, name, extension, size, modified, category, likely_purpose FROM files WHERE extension IN ('.pdf','.doc','.docx','.txt','.rtf','.eml','.msg') OR lower(name) LIKE '%ocr%' ORDER BY path", fields)
        export_query(conn, out / "entity_candidates.csv", "SELECT path, name, extension, size, modified, category, likely_purpose FROM files WHERE lower(path) LIKE '%entity%' OR lower(path) LIKE '%people%' OR lower(path) LIKE '%witness%' ORDER BY path", fields)
        export_query(conn, out / "timeline_candidates.csv", "SELECT path, name, extension, size, modified, category, likely_purpose FROM files WHERE lower(path) LIKE '%timeline%' OR lower(path) LIKE '%chronolog%' ORDER BY path", fields)
    append_log(config.audit_root, "gpt_ingest_detect_complete", status="SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
