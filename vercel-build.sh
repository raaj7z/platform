#!/bin/bash
set -e

rm -rf vendor
mkdir -p vendor

# Vendor the three supporting repositories
git clone --depth 1 https://github.com/raaj7z/DarkWeb-Deanonymization.git vendor/DarkWeb-Deanonymization
git clone --depth 1 https://github.com/raaj7z/osint-engine.git vendor/osint-engine
git clone --depth 1 https://github.com/raaj7z/Persona.git vendor/Persona

# Install complete dependencies for each module
python3 -m pip install -r vendor/DarkWeb-Deanonymization/requirements.txt
python3 -m pip install -r vendor/osint-engine/requirements.txt
python3 -m pip install -r vendor/Persona/requirements.txt

# Vercel runtime: crawler must write to /tmp instead of read-only /var/task
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
    raise SystemExit("Expected crawler config path block was not found")

path.write_text(text.replace(old, new))
print("Patched crawler runtime paths for Vercel")
PY
