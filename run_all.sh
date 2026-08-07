#!/data/data/com.termux/files/usr/bin/bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================"
echo " GitHub → GPT Ingester"
echo "======================================"
echo "Project: $SCRIPT_DIR"
echo

run_step() {
    local name="$1"
    local file="$2"

    echo "==> $name"

    if [ -f "$file" ]; then
        python "$file"
    else
        echo "Skipping ($file not found)"
    fi

    echo
}

run_step "GitHub Sync" github_sync.py
run_step "Scanner" scanner.py
run_step "Hash Index" hash_index.py
run_step "Report Generator" report_generator.py

echo "Done."
