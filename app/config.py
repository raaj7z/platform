from pathlib import Path
import os


# ---------------------------------------------------------------------------
# PRALAYX platform root
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent


def resolve_path(value: str) -> str:
    """
    Resolve a path relative to the PRALAYX platform root unless
    an absolute path is supplied.
    """
    path = Path(value)

    if path.is_absolute():
        return str(path)

    return str((BASE_DIR / path).resolve())


# ---------------------------------------------------------------------------
# PRALAYX database
# ---------------------------------------------------------------------------
#
# PRALAYX owns its own database.
#
# The crawler keeps its native crawler.db. The crawler is integrated through
# the crawler adapter and exchanges structured data with PRALAYX rather than
# having both applications blindly write to the same SQLite database.
#

DB_PATH = resolve_path(
    os.getenv(
        "PRALAYX_DB_PATH",
        "data/pralayx.db",
    )
)


# ---------------------------------------------------------------------------
# Shared schema
# ---------------------------------------------------------------------------

SCHEMA_PATH = resolve_path(
    os.getenv(
        "SHARED_SCHEMA_PATH",
        "shared/schema_sqlite.sql",
    )
)


# ---------------------------------------------------------------------------
# Crawler repository
# ---------------------------------------------------------------------------

CRAWLER_PATH = resolve_path(
    os.getenv(
        "CRAWLER_PATH",
        "../DarkWeb-Deanonymization",
    )
)


# ---------------------------------------------------------------------------
# OSINT engine repository
# ---------------------------------------------------------------------------

OSINT_ENGINE_PATH = resolve_path(
    os.getenv(
        "OSINT_ENGINE_PATH",
        "../osint-engine",
    )
)


# ---------------------------------------------------------------------------
# Web application
# ---------------------------------------------------------------------------

WEB_PATH = resolve_path(
    os.getenv(
        "PRALAYX_WEB_PATH",
        "web",
    )
)


# ---------------------------------------------------------------------------
# Report storage
# ---------------------------------------------------------------------------
#
# Every generated report is retained.
# Reports are never silently overwritten.
#

REPORTS_PATH = resolve_path(
    os.getenv(
        "PRALAYX_REPORTS_PATH",
        "data/reports",
    )
)


# ---------------------------------------------------------------------------
# Raw evidence / snapshots
# ---------------------------------------------------------------------------
#
# Raw crawler and OSINT outputs should remain available for auditability.
#

RAW_DATA_PATH = resolve_path(
    os.getenv(
        "PRALAYX_RAW_DATA_PATH",
        "data/raw",
    )
)


# ---------------------------------------------------------------------------
# Runtime configuration
# ---------------------------------------------------------------------------

HOST = os.getenv(
    "PRALAYX_HOST",
    "127.0.0.1",
)

PORT = int(
    os.getenv(
        "PRALAYX_PORT",
        "8000",
    )
)


# ---------------------------------------------------------------------------
# Crawler integration
# ---------------------------------------------------------------------------

CRAWLER_TIMEOUT = int(
    os.getenv(
        "PRALAYX_CRAWLER_TIMEOUT",
        "3600",
    )
)


# ---------------------------------------------------------------------------
# OSINT integration
# ---------------------------------------------------------------------------

OSINT_TIMEOUT = int(
    os.getenv(
        "PRALAYX_OSINT_TIMEOUT",
        "1800",
    )
)


# ---------------------------------------------------------------------------
# Terminal / event streaming
# ---------------------------------------------------------------------------

TERMINAL_POLL_INTERVAL = float(
    os.getenv(
        "PRALAYX_TERMINAL_POLL_INTERVAL",
        "0.5",
    )
)


# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------
#
# All confidence values in PRALAYX use the range 0.0 - 1.0.
#

CONFIDENCE_VERY_HIGH = 0.85
CONFIDENCE_HIGH = 0.65
CONFIDENCE_MEDIUM = 0.40


# ---------------------------------------------------------------------------
# Investigation status values
# ---------------------------------------------------------------------------

INVESTIGATION_STATUS_RUNNING = "running"
INVESTIGATION_STATUS_COMPLETED = "completed"
INVESTIGATION_STATUS_FAILED = "failed"
INVESTIGATION_STATUS_CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Session status values
# ---------------------------------------------------------------------------

SESSION_STATUS_RUNNING = "running"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_FAILED = "failed"
SESSION_STATUS_CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Run / terminal status values
# ---------------------------------------------------------------------------

RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_COMPLETED = "COMPLETED"
RUN_STATUS_NO_RESULTS = "NO_RESULTS"
RUN_STATUS_NOT_RUN = "NOT_RUN"
RUN_STATUS_MISSING_CONFIG = "MISSING_CONFIG"
RUN_STATUS_ERROR = "ERROR"
RUN_STATUS_TIMEOUT = "TIMEOUT"


# ---------------------------------------------------------------------------
# Execution types
# ---------------------------------------------------------------------------

RUN_TYPE_CRAWL = "crawl"
RUN_TYPE_OSINT = "osint"
RUN_TYPE_ANALYSIS = "analysis"
RUN_TYPE_CORRELATION = "correlation"
RUN_TYPE_MONITORING = "monitoring"


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------

REPORT_TYPE_ACTOR = "actor"
REPORT_TYPE_MISCONFIGURATION = "misconfiguration"
REPORT_TYPE_FULL = "full"
REPORT_TYPE_RAW = "raw"
REPORT_TYPE_OSINT = "osint"
REPORT_TYPE_MODULE = "module"


# ---------------------------------------------------------------------------
# Supported report formats
# ---------------------------------------------------------------------------

REPORT_FORMAT_PDF = "pdf"
REPORT_FORMAT_HTML = "html"
REPORT_FORMAT_JSON = "json"
REPORT_FORMAT_TEXT = "txt"


# ---------------------------------------------------------------------------
# Directory initialization
# ---------------------------------------------------------------------------

def ensure_runtime_directories() -> None:
    """
    Create PRALAYX-owned runtime directories.

    This function intentionally does not create or modify the crawler's
    database directories.
    """
    Path(DB_PATH).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    Path(REPORTS_PATH).mkdir(
        parents=True,
        exist_ok=True,
    )

    Path(RAW_DATA_PATH).mkdir(
        parents=True,
        exist_ok=True,
    )


# Initialize required PRALAYX directories when configuration is imported.
ensure_runtime_directories()
