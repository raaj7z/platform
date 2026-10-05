#!/usr/bin/env bash
set -e

echo "=== PRALAYX Vercel Build ==="

ROOT="$(pwd)"
VENDOR="$ROOT/vendor"

rm -rf "$VENDOR"
mkdir -p "$VENDOR"

echo "Cloning crawler..."
git clone --depth 1 https://github.com/raaj7z/DarkWeb-Deanonymization.git \
    "$VENDOR/DarkWeb-Deanonymization"

echo "Cloning OSINT engine..."
git clone --depth 1 https://github.com/raaj7z/osint-engine.git \
    "$VENDOR/osint-engine"

echo "Cloning Persona..."
git clone --depth 1 https://github.com/raaj7z/Persona.git \
    "$VENDOR/Persona"

echo "Installing Platform requirements..."
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

echo "Installing crawler requirements..."
if [ -f "$VENDOR/DarkWeb-Deanonymization/requirements.txt" ]; then
    pip install -r "$VENDOR/DarkWeb-Deanonymization/requirements.txt"
fi

echo "Installing OSINT requirements..."
if [ -f "$VENDOR/osint-engine/requirements.txt" ]; then
    pip install -r "$VENDOR/osint-engine/requirements.txt"
fi

echo "Persona heavy ML dependencies are skipped for Vercel."

# ============================================================
# VERCEL RUNTIME WRITABLE PATHS
# ============================================================
#
# Vercel's deployed application filesystem is read-only.
# The crawler currently creates data/output/log/report directories
# during import, so redirect those directories to /tmp.
#

CRAWLER_CONFIG="$VENDOR/DarkWeb-Deanonymization/src/config.py"

if [ -f "$CRAWLER_CONFIG" ]; then
    echo "Patching crawler paths for Vercel..."

    python3 - "$CRAWLER_CONFIG" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

text = text.replace(
    "DATA_DIR   = BASE_DIR / 'data'",
    "DATA_DIR   = Path('/tmp/pralayx-crawler/data')",
)

text = text.replace(
    "OUTPUT_DIR = BASE_DIR / 'output'",
    "OUTPUT_DIR = Path('/tmp/pralayx-crawler/output')",
)

text = text.replace(
    "LOG_DIR    = BASE_DIR / 'logs'",
    "LOG_DIR    = Path('/tmp/pralayx-crawler/logs')",
)

text = text.replace(
    "REPORT_DIR = BASE_DIR / 'reports'",
    "REPORT_DIR = Path('/tmp/pralayx-crawler/reports')",
)

text = text.replace(
    "DB_PATH    = DATA_DIR / 'crawler.db'",
    "DB_PATH    = DATA_DIR / 'crawler.db'",
)

path.write_text(text, encoding="utf-8")
PY

    echo "Crawler config after patch:"
    grep -E "DATA_DIR|OUTPUT_DIR|LOG_DIR|REPORT_DIR|DB_PATH" "$CRAWLER_CONFIG" || true
else
    echo "WARNING: crawler config not found: $CRAWLER_CONFIG"
fi

mkdir -p /tmp/pralayx-crawler/data
mkdir -p /tmp/pralayx-crawler/output
mkdir -p /tmp/pralayx-crawler/logs
mkdir -p /tmp/pralayx-crawler/reports

echo "=== PRALAYX Vercel Build Complete ==="
