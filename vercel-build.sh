#!/bin/bash
set -e

echo "=== PRALAYX Vercel build ==="

rm -rf vendor
mkdir -p vendor

echo "=== Cloning supporting repositories ==="

git clone --depth 1 https://github.com/raaj7z/DarkWeb-Deanonymization.git \
    vendor/DarkWeb-Deanonymization

git clone --depth 1 https://github.com/raaj7z/osint-engine.git \
    vendor/osint-engine

git clone --depth 1 https://github.com/raaj7z/Persona.git \
    vendor/Persona

echo "=== Installing Platform dependencies ==="

python3 -m pip install \
    -r requirements.txt

echo "=== Installing Crawler dependencies ==="

python3 -m pip install \
    -r vendor/DarkWeb-Deanonymization/requirements.txt

echo "=== Installing OSINT dependencies ==="

python3 -m pip install \
    -r vendor/osint-engine/requirements.txt

echo "=== Persona source included; skipping heavyweight ML dependencies ==="

# Do NOT install Persona/requirements.txt here.
# sentence-transformers pulls PyTorch and can make the Vercel
# serverless function exceed the size limit.

echo "=== Patching crawler runtime paths for Vercel ==="

python3 - <<'PY'
from pathlib import Path

path = Path("vendor/DarkWeb-Deanonymization/src/config.py")
text = path.read_text()

old = """DATA_DIR   = BASE_DIR / 'data'
OUTPUT_DIR = BASE_DIR / 'output'
LOG_DIR    = BASE_DIR / 'logs'
REPORT_DIR = BASE_DIR / 'reports'
DB_PATH    = DATA_DIR / 'crawler.db'
"""

new = """if os.getenv("VERCEL"):
    DATA_DIR   = Path("/tmp/pralayx-crawler/data")
    OUTPUT_DIR = Path("/tmp/pralayx-crawler/output")
    LOG_DIR    = Path("/tmp/pralayx-crawler/logs")
    REPORT_DIR = Path("/tmp/pralayx-crawler/reports")
else:
    DATA_DIR   = BASE_DIR / 'data'
    OUTPUT_DIR = BASE_DIR / 'output'
    LOG_DIR    = BASE_DIR / 'logs'
    REPORT_DIR = BASE_DIR / 'reports'

DB_PATH = DATA_DIR / 'crawler.db'
"""

if old not in text:
    raise SystemExit("Expected crawler config block was not found")

path.write_text(text.replace(old, new))

print("Crawler Vercel runtime paths patched.")
PY

echo "=== Build complete ==="
