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
echo "Platform Persona adapter will use the lightweight/local-compatible path."

# Vercel filesystem is read-only at runtime except /tmp.
# Redirect crawler writable data to /tmp.
CRAWLER_CONFIG="$VENDOR/DarkWeb-Deanonymization/src/config.py"

if [ -f "$CRAWLER_CONFIG" ]; then
    echo "Patching crawler writable paths..."

    python3 - "$CRAWLER_CONFIG" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

text = text.replace(
    'Path(__file__).resolve().parent.parent / "data"',
    'Path("/tmp/pralayx-crawler/data")'
)

text = text.replace(
    'Path(__file__).resolve().parent.parent / "logs"',
    'Path("/tmp/pralayx-crawler/logs")'
)

text = text.replace(
    'Path(__file__).resolve().parent.parent / "output"',
    'Path("/tmp/pralayx-crawler/output")'
)

path.write_text(text, encoding="utf-8")
PY
fi

mkdir -p /tmp/pralayx-crawler/data
mkdir -p /tmp/pralayx-crawler/logs
mkdir -p /tmp/pralayx-crawler/output

echo "=== PRALAYX Vercel Build Complete ==="
