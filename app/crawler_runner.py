from __future__ import annotations

import contextlib
import importlib
import io
import os
import sys
import traceback
from pathlib import Path


# ============================================================
# CRAWLER LOADER
# ============================================================

def load_crawler():
    """
    Load the existing DarkWeb-Deanonymization crawler.

    The crawler remains in its own repository.
    The platform only imports and controls it.
    """

    root = os.getenv(
        "CRAWLER_PATH",
        "../DarkWeb-Deanonymization",
    )

    root = os.path.abspath(root)

    src = os.path.join(root, "src")

    if not os.path.isdir(src):
        raise RuntimeError(
            f"Crawler src directory not found: {src}"
        )

    if src not in sys.path:
        sys.path.insert(0, src)

    return importlib.import_module("service")


# ============================================================
# EVENT HELPERS
# ============================================================

def _event(
    db,
    job_id,
    event_type,
    message,
    progress=None,
    payload=None,
):
    """
    Write an event into the platform job-event table.

    The frontend/WebSocket reads these events and displays
    them in the live terminal.
    """

    try:
        db.event(
            job_id,
            event_type,
            message,
            progress,
            payload,
        )
    except Exception:
        # Logging an event must never kill the crawler.
        pass


def _status(
    db,
    job_id,
    message,
    progress=None,
    payload=None,
):
    _event(
        db,
        job_id,
        "status",
        message,
        progress,
        payload,
    )


# ============================================================
# LIVE OUTPUT CAPTURE
# ============================================================

class _CrawlerOutput(io.TextIOBase):
    """
    Captures stdout/stderr produced by the crawler and sends
    each line into the platform job event stream.

    The original output is also forwarded to the real terminal.
    """

    def __init__(
        self,
        db,
        job_id,
        original,
        stream_name,
    ):
        super().__init__()

        self.db = db
        self.job_id = job_id
        self.original = original
        self.stream_name = stream_name
        self.buffer = ""

    def write(self, text):
        if not text:
            return 0

        try:
            self.original.write(text)
            self.original.flush()
        except Exception:
            pass

        self.buffer += str(text)

        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split(
                "\n",
                1,
            )

            line = line.strip()

            if line:
                _event(
                    self.db,
                    self.job_id,
                    "terminal",
                    line,
                    None,
                    {
                        "stream": self.stream_name,
                    },
                )

        return len(text)

    def flush(self):
        try:
            self.original.flush()
        except Exception:
            pass

        if self.buffer.strip():
            _event(
                self.db,
                self.job_id,
                "terminal",
                self.buffer.strip(),
                None,
                {
                    "stream": self.stream_name,
                },
            )

            self.buffer = ""


# ============================================================
# MAIN CRAWLER RUNNER
# ============================================================

def run(
    db,
    job_id,
    investigation_id,
    actor_id,
    urls,
    target=None,
    workers=3,
):
    """
    Run the real DarkWeb-Deanonymization crawler.

    Pipeline:

        Platform
          ↓
        Tor check
          ↓
        DarkCrawler
          ↓
        live events
          ↓
        crawler results
          ↓
        actor/network extraction
          ↓
        crawler reports
          ↓
        platform DB
          ↓
        completed job

    Returns the canonical platform investigation ID.
    """

    db.update_job(
        job_id,
        status="running",
        progress=0.01,
    )

    _status(
        db,
        job_id,
        "Crawler integration started",
        0.01,
        {
            "investigation_id": investigation_id,
            "actor_id": actor_id,
            "urls": urls,
        },
    )

    crawler_module = None
    result = None

    try:

        # ====================================================
        # LOAD CRAWLER
        # ====================================================

        _status(
            db,
            job_id,
            "Loading DarkWeb-Deanonymization crawler...",
            0.03,
        )

        crawler_module = load_crawler()

        _status(
            db,
            job_id,
            "Crawler service loaded",
            0.05,
        )

        # ====================================================
        # TOR CHECK
        # ====================================================

        _status(
            db,
            job_id,
            "Checking Tor connectivity...",
            0.07,
        )

        tor_ok = False
        tor_message = ""

        try:
            if hasattr(
                crawler_module,
                "check_tor",
            ):
                tor_ok, tor_message = (
                    crawler_module.check_tor()
                )
            else:
                tor_ok = True
                tor_message = (
                    "Crawler does not expose a separate "
                    "Tor check; continuing."
                )

        except Exception as exc:
            tor_ok = False
            tor_message = str(exc)

        if not tor_ok:
            raise RuntimeError(
                f"Tor connectivity check failed: "
                f"{tor_message}"
            )

        _status(
            db,
            job_id,
            f"Tor connectivity OK: {tor_message}",
            0.10,
        )

        # ====================================================
        # CRAWL START
        # ====================================================

        _status(
            db,
            job_id,
            "Starting dark-web crawler...",
            0.12,
            {
                "url_count": len(urls),
                "workers": workers,
                "target": target,
            },
        )

        # ====================================================
        # CAPTURE CRAWLER TERMINAL OUTPUT
        # ====================================================

        stdout_capture = _CrawlerOutput(
            db,
            job_id,
            sys.stdout,
            "stdout",
        )

        stderr_capture = _CrawlerOutput(
            db,
            job_id,
            sys.stderr,
            "stderr",
        )

        # ====================================================
        # RUN REAL CRAWLER
        # ====================================================

        with contextlib.redirect_stdout(
            stdout_capture
        ), contextlib.redirect_stderr(
            stderr_capture
        ):

            result = crawler_module.run_crawl(
                urls,
                target_username=target,
                workers=workers,
                use_js=False,
                rotate_circuits=True,
                session_id=None,
                db=None,
            )

        stdout_capture.flush()
        stderr_capture.flush()

        # ====================================================
        # VALIDATE RESULT
        # ====================================================

        if not isinstance(result, dict):
            raise RuntimeError(
                "Crawler returned an invalid result."
            )

        if result.get("error"):
            raise RuntimeError(
                str(result["error"])
            )

        crawler_session_id = result.get(
            "session_id"
        )

        actor_rows = result.get(
            "actor_rows",
            [],
        )

        network_rows = result.get(
            "network_rows",
            [],
        )

        crawler_results = result.get(
            "results",
            [],
        )

        _status(
            db,
            job_id,
            "Crawler collection completed",
            0.70,
            {
                "crawler_session_id":
                    crawler_session_id,
                "pages":
                    len(crawler_results),
                "actor_rows":
                    len(actor_rows),
                "network_rows":
                    len(network_rows),
            },
        )

        # ====================================================
        # REPORT GENERATION
        # ====================================================

        _status(
            db,
            job_id,
            "Generating crawler reports...",
            0.75,
        )

        report_paths = {}

        if hasattr(
            crawler_module,
            "write_session_reports",
        ):
            report_paths = (
                crawler_module.write_session_reports(
                    crawler_session_id,
                    actor_rows,
                    network_rows,
                )
                or {}
            )

        else:
            _status(
                db,
                job_id,
                "Crawler report builder is unavailable.",
                0.75,
            )

        # ====================================================
        # REPORT EVENTS
        # ====================================================

        for name, path in report_paths.items():

            _event(
                db,
                job_id,
                "report",
                f"{name}: {path}",
                0.80,
                {
                    "name": name,
                    "path": str(path),
                },
            )

        # ====================================================
        # IMPORT CRAWLER FINDINGS INTO PLATFORM
        # ====================================================

        _status(
            db,
            job_id,
            "Importing crawler findings into platform...",
            0.82,
        )

        imported = 0

        # ----------------------------------------------------
        # ACTOR FINDINGS
        # ----------------------------------------------------

        for row in actor_rows:

            if not isinstance(row, dict):
                continue

            finding_type = (
                row.get("finding_type")
                or row.get("type")
                or "other"
            )

            value = (
                row.get("value")
                or row.get("username")
                or row.get("email")
                or row.get("url")
                or row.get("domain")
            )

            if value is None:
                continue

            source = (
                row.get("source")
                or "dark-crawler"
            )

            source_url = (
                row.get("source_url")
                or row.get("url")
            )

            confidence = row.get(
                "confidence",
                0.5,
            )

            metadata = row

            try:
                db.finding(
                    investigation_id,
                    finding_type,
                    str(value),
                    source,
                    source_url,
                    confidence,
                    metadata,
                    actor_id,
                )

                imported += 1

            except Exception as exc:

                _event(
                    db,
                    job_id,
                    "warning",
                    f"Could not import actor finding: {exc}",
                    0.84,
                )

        # ----------------------------------------------------
        # NETWORK FINDINGS
        # ----------------------------------------------------

        for row in network_rows:

            if not isinstance(row, dict):
                continue

            finding_type = (
                row.get("finding_type")
                or row.get("type")
                or "infrastructure"
            )

            value = (
                row.get("value")
                or row.get("ip")
                or row.get("domain")
                or row.get("url")
                or row.get("onion_address")
            )

            if value is None:
                continue

            source = (
                row.get("source")
                or "dark-crawler"
            )

            source_url = (
                row.get("source_url")
                or row.get("url")
            )

            confidence = row.get(
                "confidence",
                0.5,
            )

            metadata = row

            try:
                db.finding(
                    investigation_id,
                    finding_type,
                    str(value),
                    source,
                    source_url,
                    confidence,
                    metadata,
                    actor_id,
                )

                imported += 1

            except Exception as exc:

                _event(
                    db,
                    job_id,
                    "warning",
                    f"Could not import network finding: {exc}",
                    0.88,
                )

        # ====================================================
        # MAP CRAWLER SESSION
        # ====================================================

        try:

            db.update_investigation(
                investigation_id,
                status="completed",
                crawler_session_id=
                    crawler_session_id,
            )

        except TypeError:

            # Compatibility with older DB implementations.
            db.update_investigation(
                investigation_id,
                status="completed",
            )

        # ====================================================
        # COMPLETE JOB
        # ====================================================

        result_ref = (
            crawler_session_id
            or investigation_id
        )

        db.update_job(
            job_id,
            status="completed",
            progress=1.0,
            result_ref=result_ref,
        )

        _event(
            db,
            job_id,
            "completed",
            "Crawler completed successfully",
            1.0,
            {
                "investigation_id":
                    investigation_id,
                "crawler_session_id":
                    crawler_session_id,
                "actor_findings":
                    len(actor_rows),
                "network_findings":
                    len(network_rows),
                "imported_findings":
                    imported,
                "reports":
                    report_paths,
            },
        )

        return investigation_id

    # ========================================================
    # FAILURE
    # ========================================================

    except Exception as exc:

        error_message = (
            f"{type(exc).__name__}: {exc}"
        )

        traceback_text = traceback.format_exc()

        _event(
            db,
            job_id,
            "error",
            error_message,
            1.0,
            {
                "traceback": traceback_text,
            },
        )

        try:
            db.update_investigation(
                investigation_id,
                status="failed",
            )
        except Exception:
            pass

        try:
            db.update_job(
                job_id,
                status="failed",
                progress=1.0,
                error=error_message,
            )
        except Exception:
            pass

        raise
