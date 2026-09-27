"""
PRALAYX crawler integration layer.

Responsibilities
----------------
1. Start a PRALAYX crawler session/run.
2. Execute the real DarkWeb-Deanonymization crawler.
3. Stream crawler stdout/stderr into PRALAYX terminal events.
4. Preserve the crawler's native database.
5. Import normalized crawler findings into the PRALAYX database.
6. Preserve raw crawler results as immutable snapshots.
7. Register every crawler-generated report in PRALAYX report history.
8. Maintain investigation/session/run/job lifecycle state.

Important
---------
The crawler owns its own native database.

DO NOT pass the PRALAYX DB object to DarkWeb-Deanonymization.

The integration boundary is:

    PRALAYX
       |
       | session_id
       v
    DarkWeb-Deanonymization
       |
       | results / actor_rows / network_rows / reports
       v
    PRALAYX normalization + evidence store
"""

from __future__ import annotations

import contextlib
import importlib
import io
import os
import sys
import traceback
from pathlib import Path
from typing import Any


# ============================================================
# CRAWLER LOADER
# ============================================================

def load_crawler():
    """
    Load the existing DarkWeb-Deanonymization service module.

    The crawler remains an independent repository.
    PRALAYX controls it through service.py.
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
# BASIC HELPERS
# ============================================================

def _safe_float(value: Any, default: float = 0.5) -> float:
    """
    Normalize confidence to the PRALAYX 0.0-1.0 scale.

    Older crawler components may occasionally return:
        55
        80
        95

    which represent percentages rather than normalized values.
    """

    try:
        value = float(value)
    except (TypeError, ValueError):
        return default

    if value > 1.0:
        value /= 100.0

    return max(0.0, min(1.0, value))


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    return text if text else None


def _first_value(row: dict, *keys: str) -> Any:
    for key in keys:
        value = row.get(key)

        if value is not None:
            if isinstance(value, str):
                if value.strip():
                    return value.strip()
            else:
                return value

    return None


# ============================================================
# TERMINAL EVENT HELPERS
# ============================================================

def _event(
    db,
    job_id: str,
    event_type: str,
    message: str,
    progress: float | None = None,
    payload: dict | None = None,
    run_id: str | None = None,
):
    """
    Persist one terminal/audit event.

    Event failure must never terminate the crawler.
    """

    try:
        return db.event(
            job_id=job_id,
            event_type=event_type,
            message=message,
            progress=progress,
            payload=payload,
            run_id=run_id,
        )
    except Exception:
        return None


def _status(
    db,
    job_id: str,
    message: str,
    progress: float | None = None,
    payload: dict | None = None,
    run_id: str | None = None,
):
    return _event(
        db,
        job_id,
        "status",
        message,
        progress,
        payload,
        run_id,
    )


# ============================================================
# LIVE CRAWLER OUTPUT CAPTURE
# ============================================================

class _CrawlerOutput(io.TextIOBase):
    """
    Capture crawler stdout/stderr.

    Every completed line becomes a PRALAYX terminal event while
    still being forwarded to the original process stream.
    """

    def __init__(
        self,
        db,
        job_id: str,
        original,
        stream_name: str,
        run_id: str | None = None,
    ):
        super().__init__()

        self.db = db
        self.job_id = job_id
        self.original = original
        self.stream_name = stream_name
        self.run_id = run_id
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

            if not line:
                continue

            _event(
                self.db,
                self.job_id,
                "terminal",
                line,
                None,
                {
                    "stream": self.stream_name,
                },
                self.run_id,
            )

        return len(text)

    def flush(self):
        try:
            self.original.flush()
        except Exception:
            pass

        remaining = self.buffer.strip()

        if remaining:
            _event(
                self.db,
                self.job_id,
                "terminal",
                remaining,
                None,
                {
                    "stream": self.stream_name,
                },
                self.run_id,
            )

        self.buffer = ""


# ============================================================
# REPORT REGISTRATION
# ============================================================

def _register_report(
    db,
    investigation_id: str,
    run_id: str,
    path: Any,
    report_type: str,
    stage: str = "crawl",
    module_id: str = "darkweb-crawler",
):
    """
    Register one native crawler report in PRALAYX history.

    The file itself remains in the crawler repository/output tree.
    PRALAYX stores its metadata so the report remains discoverable.
    """

    if not path:
        return None

    try:
        report_path = Path(path).resolve()

        if not report_path.exists():
            return None

        if not report_path.is_file():
            return None

        suffix = report_path.suffix.lower().lstrip(".")

        report_format = suffix or "unknown"

        mime_map = {
            "json": "application/json",
            "jsonl": "application/jsonl",
            "csv": "text/csv",
            "html": "text/html",
            "htm": "text/html",
            "pdf": "application/pdf",
            "txt": "text/plain",
        }

        mime_type = mime_map.get(
            suffix,
            "application/octet-stream",
        )

        return db.register_report(
            investigation_id=investigation_id,
            stage=stage,
            report_type=report_type,
            report_format=report_format,
            file_name=report_path.name,
            file_path=str(report_path),
            file_size=report_path.stat().st_size,
            mime_type=mime_type,
            run_id=run_id,
            module_id=module_id,
            status="completed",
        )

    except Exception:
        return None


def _register_reports(
    db,
    investigation_id: str,
    run_id: str,
    report_paths: Any,
):
    """
    Register all report paths returned by the crawler.

    Supports:
        dict
        list
        tuple
        single path
    """

    registered = []

    if not report_paths:
        return registered

    if isinstance(report_paths, dict):
        items = report_paths.items()
    elif isinstance(report_paths, (list, tuple)):
        items = [
            (Path(path).stem, path)
            for path in report_paths
        ]
    else:
        items = [
            (
                Path(str(report_paths)).stem,
                report_paths,
            )
        ]

    for name, path in items:
        label = str(name).lower()

        if "actor" in label:
            report_type = "actor_report"

        elif "network" in label:
            report_type = "misconfiguration_report"

        elif "full" in label:
            report_type = "full_report"

        elif "raw" in label:
            report_type = "raw_report"

        else:
            report_type = "crawler_report"

        report_id = _register_report(
            db=db,
            investigation_id=investigation_id,
            run_id=run_id,
            path=path,
            report_type=report_type,
        )

        if report_id:
            registered.append(
                {
                    "report_id": report_id,
                    "name": str(name),
                    "path": str(path),
                    "report_type": report_type,
                }
            )

    return registered


# ============================================================
# FINDING IMPORT
# ============================================================

def _import_actor_row(
    db,
    investigation_id: str,
    run_id: str,
    actor_id: str | None,
    row: dict,
):
    """
    Import one actor/OSINT row.

    The row is retained inside finding metadata, while the
    important identifier is also inserted into the identifier
    and entity-sighting layers.
    """

    finding_type = _first_value(
        row,
        "finding_type",
        "entity_type",
        "type",
    ) or "other"

    value = _first_value(
        row,
        "value",
        "normalized",
        "username",
        "handle",
        "email",
        "wallet_address",
        "pgp",
        "telegram",
        "jabber",
        "url",
        "domain",
    )

    if value is None:
        return None

    value = str(value)

    source = (
        _first_value(
            row,
            "source",
            "platform",
        )
        or "darkweb-crawler"
    )

    source_url = _first_value(
        row,
        "source_url",
        "url",
    )

    confidence = _safe_float(
        row.get("confidence"),
        0.5,
    )

    finding_id = db.add_finding(
        investigation_id=investigation_id,
        finding_type=str(finding_type),
        value=value,
        source=str(source),
        source_url=_safe_text(source_url),
        confidence=confidence,
        metadata=row,
        actor_id=actor_id,
        run_id=run_id,
    )

    normalized = _first_value(
        row,
        "normalized",
        "normalized_value",
    )

    db.add_identifier(
        investigation_id=investigation_id,
        identifier_type=str(finding_type),
        value=value,
        actor_id=actor_id,
        normalized_value=(
            str(normalized)
            if normalized is not None
            else value
        ),
        source=str(source),
        source_url=_safe_text(source_url),
        confidence=confidence,
    )

    source_id = db.get_or_create_source(
        name=str(source),
        url=_safe_text(source_url),
        source_type="crawler",
    )

    db.add_entity_sighting(
        investigation_id=investigation_id,
        entity_type=str(finding_type),
        normalized_value=(
            str(normalized)
            if normalized is not None
            else value
        ),
        raw_value=value,
        source_id=source_id,
        source_url=_safe_text(source_url),
        actor_id=actor_id,
        run_id=run_id,
        confidence=confidence,
        metadata=row,
    )

    return finding_id


def _import_network_row(
    db,
    investigation_id: str,
    run_id: str,
    actor_id: str | None,
    row: dict,
):
    """
    Import one infrastructure/network artifact.

    Network artifacts remain evidence. They are not automatically
    treated as proof of actor attribution.
    """

    finding_type = _first_value(
        row,
        "finding_type",
        "artifact_type",
        "type",
    ) or "infrastructure"

    value = _first_value(
        row,
        "value",
        "ip",
        "ip_address",
        "domain",
        "host",
        "url",
        "onion_address",
        "server_software",
        "banner",
    )

    if value is None:
        return None

    value = str(value)

    source = (
        _first_value(
            row,
            "source",
            "platform",
        )
        or "darkweb-crawler"
    )

    source_url = _first_value(
        row,
        "source_url",
        "url",
    )

    confidence = _safe_float(
        row.get("confidence"),
        0.5,
    )

    finding_id = db.add_finding(
        investigation_id=investigation_id,
        finding_type=str(finding_type),
        value=value,
        source=str(source),
        source_url=_safe_text(source_url),
        confidence=confidence,
        metadata=row,
        actor_id=actor_id,
        run_id=run_id,
    )

    source_id = db.get_or_create_source(
        name=str(source),
        url=_safe_text(source_url),
        source_type="crawler",
    )

    db.add_entity_sighting(
        investigation_id=investigation_id,
        entity_type=str(finding_type),
        normalized_value=value.lower(),
        raw_value=value,
        source_id=source_id,
        source_url=_safe_text(source_url),
        actor_id=actor_id,
        run_id=run_id,
        confidence=confidence,
        metadata=row,
    )

    return finding_id


# ============================================================
# MAIN CRAWLER RUNNER
# ============================================================

def run(
    db,
    job_id: str,
    investigation_id: str,
    actor_id: str | None,
    urls: list[str],
    target: str | None = None,
    workers: int = 3,
):
    """
    Execute one real crawler run.

    PRALAYX lifecycle:

        investigation
            ↓
        platform session
            ↓
        platform run
            ↓
        platform job
            ↓
        real crawler
            ↓
        raw snapshot
            ↓
        normalized findings
            ↓
        report registry
            ↓
        completed / no-results / failed
    """

    if not urls:
        raise ValueError(
            "At least one crawl URL is required."
        )

    # --------------------------------------------------------
    # Create PRALAYX session/run.
    # --------------------------------------------------------

    session_id = db.create_session(
        investigation_id=investigation_id,
        session_type="crawl",
        actor_id=actor_id,
        metadata={
            "target": target,
            "url_count": len(urls),
            "workers": workers,
        },
    )

    run_id = db.create_run(
        investigation_id=investigation_id,
        run_type="crawler",
        session_id=session_id,
        module_id="darkweb-crawler",
        actor_id=actor_id,
        payload={
            "urls": urls,
            "target": target,
            "workers": workers,
        },
    )

    _status(
        db,
        job_id,
        "Crawler integration started",
        0.01,
        {
            "investigation_id": investigation_id,
            "session_id": session_id,
            "run_id": run_id,
            "actor_id": actor_id,
            "url_count": len(urls),
        },
        run_id,
    )

    db.add_timeline_event(
        investigation_id=investigation_id,
        event_type="crawl_started",
        message="Dark-web crawler started",
        session_id=session_id,
        run_id=run_id,
        actor_id=actor_id,
        payload={
            "url_count": len(urls),
            "target": target,
        },
    )

    crawler_module = None

    try:
        # ----------------------------------------------------
        # Load crawler service.
        # ----------------------------------------------------

        _status(
            db,
            job_id,
            "Loading DarkWeb-Deanonymization crawler...",
            0.03,
            run_id=run_id,
        )

        crawler_module = load_crawler()

        _status(
            db,
            job_id,
            "Crawler service loaded",
            0.05,
            run_id=run_id,
        )

        # ----------------------------------------------------
        # Tor check.
        # ----------------------------------------------------

        _status(
            db,
            job_id,
            "Checking Tor connectivity...",
            0.07,
            run_id=run_id,
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
                    "Crawler service does not expose "
                    "a dedicated Tor check."
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
            run_id=run_id,
        )

        # ----------------------------------------------------
        # Run the actual crawler.
        #
        # IMPORTANT:
        # db=None is intentional.
        #
        # The crawler must continue using its own native DB.
        # ----------------------------------------------------

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
            run_id,
        )

        stdout_capture = _CrawlerOutput(
            db,
            job_id,
            sys.stdout,
            "stdout",
            run_id,
        )

        stderr_capture = _CrawlerOutput(
            db,
            job_id,
            sys.stderr,
            "stderr",
            run_id,
        )

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
                rotate_every=10,
                session_id=session_id,
                db=None,
            )

        stdout_capture.flush()
        stderr_capture.flush()

        # ----------------------------------------------------
        # Validate crawler response.
        # ----------------------------------------------------

        if not isinstance(result, dict):
            raise RuntimeError(
                "Crawler returned an invalid result object."
            )

        if result.get("error"):
            raise RuntimeError(
                str(result["error"])
            )

        crawler_session_id = (
            result.get("session_id")
            or session_id
        )

        crawler_results = (
            result.get("results")
            or []
        )

        actor_rows = (
            result.get("actor_rows")
            or []
        )

        network_rows = (
            result.get("network_rows")
            or []
        )

        # ----------------------------------------------------
        # Preserve complete raw crawler result.
        # ----------------------------------------------------

        db.add_raw_snapshot(
            investigation_id=investigation_id,
            session_id=session_id,
            run_id=run_id,
            source="darkweb-crawler",
            snapshot_type="crawler_result",
            payload=result,
        )

        _status(
            db,
            job_id,
            "Crawler collection completed",
            0.70,
            {
                "crawler_session_id": crawler_session_id,
                "pages": len(crawler_results),
                "actor_rows": len(actor_rows),
                "network_rows": len(network_rows),
            },
            run_id,
        )

        # ----------------------------------------------------
        # Import actor findings.
        # ----------------------------------------------------

        imported_actor = 0

        for row in actor_rows:
            if not isinstance(row, dict):
                continue

            finding_id = _import_actor_row(
                db=db,
                investigation_id=investigation_id,
                run_id=run_id,
                actor_id=actor_id,
                row=row,
            )

            if finding_id:
                imported_actor += 1

        # ----------------------------------------------------
        # Import network findings.
        # ----------------------------------------------------

        imported_network = 0

        for row in network_rows:
            if not isinstance(row, dict):
                continue

            finding_id = _import_network_row(
                db=db,
                investigation_id=investigation_id,
                run_id=run_id,
                actor_id=actor_id,
                row=row,
            )

            if finding_id:
                imported_network += 1

        imported_total = (
            imported_actor
            + imported_network
        )

        # ----------------------------------------------------
        # Update investigation linkage.
        # ----------------------------------------------------

        db.update_investigation(
            investigation_id,
            crawler_session_id=crawler_session_id,
        )

        # ----------------------------------------------------
        # Register native crawler reports.
        # ----------------------------------------------------

        _status(
            db,
            job_id,
            "Registering crawler reports...",
            0.90,
            run_id=run_id,
        )

        report_paths = {}

        try:
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
        except Exception as exc:
            _event(
                db,
                job_id,
                "warning",
                f"Crawler report generation failed: {exc}",
                0.90,
                run_id=run_id,
            )

        registered_reports = _register_reports(
            db=db,
            investigation_id=investigation_id,
            run_id=run_id,
            report_paths=report_paths,
        )

        for report in registered_reports:
            _event(
                db,
                job_id,
                "report",
                (
                    f"Report registered: "
                    f"{report['name']}"
                ),
                0.94,
                report,
                run_id,
            )

        # ----------------------------------------------------
        # Determine truthful terminal state.
        # ----------------------------------------------------

        if imported_total == 0:
            final_status = "NO_RESULTS"
            final_message = (
                "Crawler completed but produced "
                "no normalized findings."
            )
        else:
            final_status = "COMPLETED"
            final_message = (
                "Crawler completed successfully."
            )

        db.update_session(
            session_id,
            status=final_status,
            metadata={
                "crawler_session_id": crawler_session_id,
                "actor_rows": len(actor_rows),
                "network_rows": len(network_rows),
                "imported_actor": imported_actor,
                "imported_network": imported_network,
                "report_count": len(
                    registered_reports
                ),
            },
        )

        db.update_run(
            run_id,
            status=final_status,
            progress=1.0,
            result_ref=crawler_session_id,
        )

        db.update_job(
            job_id,
            status=final_status,
            progress=1.0,
            result_ref=run_id,
        )

        db.update_investigation(
            investigation_id,
            status="completed",
        )

        db.add_timeline_event(
            investigation_id=investigation_id,
            event_type="crawl_completed",
            message=final_message,
            session_id=session_id,
            run_id=run_id,
            actor_id=actor_id,
            payload={
                "crawler_session_id":
                    crawler_session_id,
                "actor_rows":
                    len(actor_rows),
                "network_rows":
                    len(network_rows),
                "imported_actor":
                    imported_actor,
                "imported_network":
                    imported_network,
                "reports":
                    registered_reports,
                "status":
                    final_status,
            },
        )

        _event(
            db,
            job_id,
            "completed",
            final_message,
            1.0,
            {
                "status": final_status,
                "investigation_id":
                    investigation_id,
                "session_id":
                    session_id,
                "run_id":
                    run_id,
                "crawler_session_id":
                    crawler_session_id,
                "actor_findings":
                    len(actor_rows),
                "network_findings":
                    len(network_rows),
                "imported_findings":
                    imported_total,
                "reports":
                    registered_reports,
            },
            run_id,
        )

        return {
            "investigation_id": investigation_id,
            "session_id": session_id,
            "run_id": run_id,
            "crawler_session_id":
                crawler_session_id,
            "status": final_status,
            "actor_rows": len(actor_rows),
            "network_rows": len(network_rows),
            "imported_findings":
                imported_total,
            "reports":
                registered_reports,
        }

    except Exception as exc:
        error_message = (
            f"{type(exc).__name__}: {exc}"
        )

        traceback_text = (
            traceback.format_exc()
        )

        # ----------------------------------------------------
        # Preserve failure as evidence/audit information.
        # ----------------------------------------------------

        _event(
            db,
            job_id,
            "error",
            error_message,
            1.0,
            {
                "traceback":
                    traceback_text,
                "investigation_id":
                    investigation_id,
            },
            run_id,
        )

        try:
            db.add_raw_snapshot(
                investigation_id=investigation_id,
                session_id=session_id,
                run_id=run_id,
                source="darkweb-crawler",
                snapshot_type="crawler_error",
                payload={
                    "error": error_message,
                    "traceback": traceback_text,
                },
            )
        except Exception:
            pass

        try:
            db.update_session(
                session_id,
                status="ERROR",
                metadata={
                    "error": error_message,
                },
            )
        except Exception:
            pass

        try:
            db.update_run(
                run_id,
                status="ERROR",
                progress=1.0,
                error=error_message,
            )
        except Exception:
            pass

        try:
            db.update_job(
                job_id,
                status="ERROR",
                progress=1.0,
                error=error_message,
            )
        except Exception:
            pass

        try:
            db.update_investigation(
                investigation_id,
                status="failed",
            )
        except Exception:
            pass

        try:
            db.add_timeline_event(
                investigation_id=investigation_id,
                event_type="crawl_failed",
                message=error_message,
                session_id=session_id,
                run_id=run_id,
                actor_id=actor_id,
                payload={
                    "traceback":
                        traceback_text,
                },
            )
        except Exception:
            pass

        raise
