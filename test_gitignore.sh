#!/data/data/com.termux/files/usr/bin/bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: $SCRIPT_DIR is not a Git repository."
    exit 1
fi

echo "Repository:"
git rev-parse --show-toplevel
echo

PASS=0
FAIL=0

pass() {
    echo "[PASS] $1"
    PASS=$((PASS+1))
}

fail() {
    echo "[FAIL] $1"
    FAIL=$((FAIL+1))
}

check_ignored() {
    if git check-ignore -q "$1"; then
        pass "$1"
    else
        fail "$1"
    fi
}

check_tracked() {
    if git check-ignore -q "$1"; then
        fail "$1"
    else
        pass "$1"
    fi
}

mkdir -p logs reports output cache db

touch .env
touch logs/test.log
touch reports/report.html
touch output/test.bin
touch cache/test.cache
touch db/test.db

touch README.txt CHANGELOG.txt VERSION.txt notes.txt

check_ignored ".env"
check_ignored "logs/test.log"
check_ignored "reports/report.html"
check_ignored "output/test.bin"
check_ignored "cache/test.cache"
check_ignored "db/test.db"

check_tracked "README.txt"
check_tracked "CHANGELOG.txt"
check_tracked "VERSION.txt"
check_tracked "notes.txt"

echo
echo "PASS: $PASS"
echo "FAIL: $FAIL"

exit $FAIL
