#!/bin/bash
set -e

rm -rf vendor
mkdir -p vendor

# Vendor the supporting repositories.
git clone --depth 1 https://github.com/raaj7z/DarkWeb-Deanonymization.git vendor/DarkWeb-Deanonymization
git clone --depth 1 https://github.com/raaj7z/osint-engine.git vendor/osint-engine
git clone --depth 1 https://github.com/raaj7z/Persona.git vendor/Persona

# Install only the dependencies needed by the Vercel runtime.
# Do NOT install Persona's full ML stack here.
python3 -m pip install -r vendor/DarkWeb-Deanonymization/requirements.txt
python3 -m pip install -r vendor/osint-engine/requirements.txt

# Persona source is included for compatibility, but its heavyweight
# sentence-transformers / PyTorch stack is intentionally not installed
# in the Vercel function.
#
# Local WSL Persona installation remains unchanged.

# Vercel filesystem is read-only except /tmp.
# Redirect crawler runtime data to /tmp.
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
print("Patched crawler runtime paths for Vercel")
PY
