#!/usr/bin/env bash
set -Eeuo pipefail

PROGRAM="$(basename "$0")"
VERSION="2026.06.01"

INPUT=""
OUTPUT=""
RECURSIVE=0
FORCE_OCR=0
DRY_RUN=0
WORKERS=""
VERIFY=0
LEGAL_REPORTS=0
PROGRESS_EVERY=1
RESUME=1

HOSTNAME_VALUE="$(hostname 2>/dev/null || printf 'unknown')"
USERNAME_VALUE="$(whoami 2>/dev/null || printf 'unknown')"
RUN_ID="$(date -u +%Y%m%d_%H%M%S)"


trap 'echo "[WARN] SIGTSTP received" >> "$MASTER_LOG"' SIGTSTP
trap 'echo "[WARN] SIGCONT received" >> "$MASTER_LOG"' SIGCONT


MASTER_LOG=""
MANIFEST_JSONL=""
STATUS_JSON=""
STATUS_TXT=""
PROCESS_RESULT=""
INDEX_DB="${GPT_INGEST_DB:-$HOME/.local/share/gpt_ingest/ingest_index.sqlite}"

usage() {
    cat <<EOF
Usage: $PROGRAM [--input PATH] [--output DIR] [options]

Forensic GPT document ingestion for PDF, TIFF, JPG, PNG, and ZIP archives.
Directory input scans the selected folder for matching document files, including *.pdf.

Options:
  --input PATH       File or directory to process. Defaults to current directory.
  --output DIR       Output directory. Defaults to INPUT directory/GPT_INGEST.
  --recursive        Recursively traverse directories.
  --force-ocr        Force OCR even when a PDF already has text.
                     Also bypasses the completed-file database.
  --dry-run          Print planned actions without writing outputs.
  --workers N        OCR worker count passed to ocrmypdf. Defaults to CPU count minus one.
  --progress-every N Print/write progress every N discovered items. Defaults to 1.
  --no-resume        Do not skip documents already completed in the resume database.
  --verify           Run validation checks and report status.
  --report           Generate legal-review starter files.
  -h, --help         Show this help.

Output tree:
  GPT_INGEST/source ocr text metadata logs hashes reports manifests
  Multi-document runs also create text/COMBINED_GPT_UPLOAD_<run_id>.txt.
Resume database:
  $INDEX_DB
EOF
}

Die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

utc_now() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}

shell_quote() {
    printf '%q ' "$@"
}

sanitize_name() {
    local name="$1"
    local base ext
    if [[ "$name" == *.* ]]; then
        base="${name%.*}"
        ext=".${name##*.}"
    else
        base="$name"
        ext=""
    fi

    base="$(printf '%s' "$base" | sed -E 's/[,;]/_/g; s/[[:space:]]+/_/g; s/_+/_/g; s/^_//; s/_$//')"
    [[ -n "$base" ]] || base="document"
    printf '%s%s' "$base" "$ext"
}

lower_ext() {
    local name="$1"
    local ext="${name##*.}"
    [[ "$name" == "$ext" ]] && return 0
    printf '%s' "$ext" | tr '[:upper:]' '[:lower:]'
}

is_supported_document() {
    case "$(lower_ext "$1")" in
        pdf|tif|tiff|jpg|jpeg|png) return 0 ;;
        *) return 1 ;;
    esac
}

is_zip() {
    [[ "$(lower_ext "$1")" == "zip" ]]
}

should_skip_discovered_file() {
    local file="$1"
    local output_root="$2"
    local resolved_file name_lower

    resolved_file="$(realpath -m -- "$file")"
    if [[ "$resolved_file" == "$output_root"/* ]]; then
        return 0
    fi

    name_lower="$(basename "$file" | tr '[:upper:]' '[:lower:]')"
    if [[ "$name_lower" == *_ocr.pdf ]]; then
        return 0
    fi

    return 1
}

require_positive_int() {
    local value="$1"
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || die "--workers must be a positive integer"
}

default_workers() {
    local cpus
    cpus="$(nproc 2>/dev/null || printf '1')"
    if (( cpus > 1 )); then
        printf '%s' "$((cpus - 1))"
    else
        printf '1'
    fi
}

resolve_paths() {
    INPUT="$(realpath -- "$INPUT")"
    if [[ -n "$OUTPUT" ]]; then
        OUTPUT="$(realpath -m -- "$OUTPUT")"
    fi
    [[ -n "$WORKERS" ]] || WORKERS="$(default_workers)"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --input)
                [[ $# -ge 2 ]] || die "--input requires a value"
                INPUT="$2"
                shift 2
                ;;
            --output)
                [[ $# -ge 2 ]] || die "--output requires a value"
                OUTPUT="$2"
                shift 2
                ;;
            --recursive)
                RECURSIVE=1
                shift
                ;;
            --force-ocr)
                FORCE_OCR=1
                shift
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --workers)
                [[ $# -ge 2 ]] || die "--workers requires a value"
                require_positive_int "$2"
                WORKERS="$2"
                shift 2
                ;;
            --progress-every)
                [[ $# -ge 2 ]] || die "--progress-every requires a value"
                require_positive_int "$2"
                PROGRESS_EVERY="$2"
                shift 2
                ;;
            --no-resume)
                RESUME=0
                shift
                ;;
            --verify)
                VERIFY=1
                shift
                ;;
            --report)
                LEGAL_REPORTS=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                if [[ -z "$INPUT" && -e "$1" ]]; then
                    INPUT="$1"
                    shift
                else
                    die "Unknown argument: $1"
                fi
                ;;
        esac
    done

    if [[ -n "$INPUT" && ! -e "$INPUT" ]]; then
        die "Input not found: $INPUT"
    fi
}

default_output_dir() {
    if [[ -n "$OUTPUT" ]]; then
        printf '%s' "$OUTPUT"
    elif [[ -d "$INPUT" ]]; then
        printf '%s/GPT_INGEST' "$INPUT"
    else
        printf '%s/GPT_INGEST' "$(dirname "$INPUT")"
    fi
}

interactive_select_paths() {
    local candidates=()
    local labels=()
    local found choice selected default_out output_answer

    printf 'GPT Ingest input selection\n'
    printf 'Current directory: %s\n\n' "$PWD"

    candidates+=("$PWD")
    labels+=("Current directory")

    while IFS= read -r -d '' found; do
        candidates+=("$found")
        labels+=("Directory: ./$(basename "$found")")
    done < <(find "$PWD" -maxdepth 1 -mindepth 1 -type d ! -name 'GPT_INGEST' -print0 | sort -z)

    while IFS= read -r -d '' found; do
        candidates+=("$found")
        labels+=("File: ./$(basename "$found")")
    done < <(find "$PWD" -maxdepth 1 -type f \( \
        -iname '*.pdf' -o -iname '*.tif' -o -iname '*.tiff' -o \
        -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o \
        -iname '*.zip' \
    \) -print0 | sort -z)

    local i
    for i in "${!candidates[@]}"; do
        printf '  %d) %s\n' "$((i + 1))" "${labels[$i]}"
    done

    printf '\nSelect input number, or type a path [1]: '
    IFS= read -r choice
    choice="${choice:-1}"

    if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#candidates[@]} )); then
        selected="${candidates[$((choice - 1))]}"
    else
        selected="$choice"
    fi

    [[ -e "$selected" ]] || die "Selected input not found: $selected"
    INPUT="$selected"

    default_out="$PWD/GPT_INGEST"
    printf 'Output directory [%s]: ' "$default_out"
    IFS= read -r output_answer
    OUTPUT="${output_answer:-$default_out}"
}

make_output_tree() {
    local out="$1"
    if (( DRY_RUN )); then
        printf '[DRY-RUN] Would create output tree at %s\n' "$out"
        return 0
    fi

    mkdir -p \
        "$out/source" \
        "$out/ocr" \
        "$out/text" \
        "$out/metadata" \
        "$out/logs" \
        "$out/hashes" \
        "$out/reports" \
        "$out/manifests" \
        "$out/.tmp"

    MASTER_LOG="$out/logs/forensic_${RUN_ID}.log"
    MANIFEST_JSONL="$out/manifests/manifest_${RUN_ID}.jsonl"
    STATUS_JSON="$out/logs/current_status.json"
    STATUS_TXT="$out/logs/current_status.txt"
    : > "$MASTER_LOG"
    : > "$MANIFEST_JSONL"
    write_progress_status "setup" 0 0 0 "" "START" "output tree ready"
}

init_resume_db() {
    if (( DRY_RUN )); then
        return 0
    fi

    mkdir -p "$(dirname "$INDEX_DB")"
    python3 - "$INDEX_DB" <<'PY'
import sqlite3
import sys

db = sys.argv[1]
with sqlite3.connect(db) as conn:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            source_sha256 TEXT PRIMARY KEY,
            original_name TEXT NOT NULL,
            first_source_path TEXT NOT NULL,
            last_source_path TEXT NOT NULL,
            source_size INTEGER,
            source_mtime INTEGER,
            source_copy TEXT,
            ocr_pdf TEXT,
            text_file TEXT,
            metadata_json TEXT,
            pdfinfo_file TEXT,
            exif_file TEXT,
            validation_report TEXT,
            hash_file TEXT,
            status TEXT NOT NULL,
            first_seen_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_utc TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
PY
}

snapshot_resume_db() {
    local output_root="$1"

    if (( DRY_RUN )) || [[ ! -f "$INDEX_DB" ]]; then
        return 0
    fi

    cp -p -- "$INDEX_DB" "$output_root/manifests/ingest_index_${RUN_ID}.sqlite" || true
}

import_existing_output_index() {
    local output_root="$1"

    if (( DRY_RUN )) || [[ ! -d "$output_root/metadata" ]]; then
        return 0
    fi

    python3 - "$INDEX_DB" "$output_root/metadata" <<'PY'
import glob
import json
import os
import sqlite3
import sys

db, metadata_dir = sys.argv[1:]
paths = sorted(glob.glob(os.path.join(metadata_dir, "*.json")))
if not paths:
    sys.exit(0)

with sqlite3.connect(db) as conn:
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        if record.get("status") != "SUCCESS":
            continue

        files = record.get("files", {})
        hashes = record.get("hashes", {})
        source_hash = hashes.get("source_copy_sha256") or hashes.get("source_sha256")
        if not source_hash:
            continue

        source_copy = files.get("source_copy") or ""
        ocr_pdf = files.get("ocr_pdf") or ""
        text_file = files.get("text") or ""
        metadata_json = path
        pdfinfo_file = files.get("pdfinfo") or ""
        exif_file = files.get("exiftool") or ""
        validation_report = files.get("validation_report") or ""

        if not (os.path.exists(ocr_pdf) and os.path.exists(text_file)):
            continue
