

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Report splitting
# ---------------------------------------------------------------------------

def network(report: dict[str, Any]) -> dict[str, Any]:
    """
    Return infrastructure/network findings.
    """
    findings = report.get("findings") or []

    return {
        "investigation_id": report.get("investigation_id"),
        "items": [
            finding
            for finding in findings
            if finding.get("finding_type") == "infrastructure"
        ],
    }


def actor(report: dict[str, Any]) -> dict[str, Any]:
    """
    Return actor/persona-related findings.
    """
    findings = report.get("findings") or []

    return {
        "investigation_id": report.get("investigation_id"),
        "items": [
            finding
            for finding in findings
            if finding.get("finding_type") != "infrastructure"
        ],
    }


def full(report: dict[str, Any]) -> dict[str, Any]:
    """
    Return the complete report without filtering.
    """
    return dict(report)


def raw(report: dict[str, Any]) -> dict[str, Any]:
    """
    Preserve the complete raw report object.
    """
    return {
        "investigation_id": report.get("investigation_id"),
        "raw": report,
    }


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _json_default(value: Any) -> str:
    return str(value)


def json_bytes(data: Any) -> bytes:
    return json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")


def csv_bytes(
    rows: Iterable[dict[str, Any]],
) -> bytes:
    """
    Convert arbitrary finding rows to CSV.

    Nested dictionaries/lists are preserved as JSON strings rather than
    being silently discarded.
    """
    rows = list(rows or [])

    if not rows:
        return b""

    fields = sorted(
        {
            key
            for row in rows
            for key in row.keys()
        }
    )

    out = io.StringIO()

    writer = csv.DictWriter(
        out,
        fieldnames=fields,
        extrasaction="ignore",
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(
            {
                key: (
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        default=_json_default,
                    )
                    if isinstance(value, (dict, list, tuple))
                    else value
                )
                for key, value in row.items()
            }
        )

    return out.getvalue().encode("utf-8")


def html_report(
    title: str,
    data: Any,
) -> bytes:
    """
    Generate a self-contained HTML report.
    """
    serialized = json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
        default=_json_default,
    )

    escaped_title = html.escape(
        str(title),
    )

    escaped_data = html.escape(
        serialized,
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escaped_title}</title>
<style>
:root {{
    color-scheme: dark;
}}

body {{
    margin: 0;
    padding: 32px;
    background: #0b0d10;
    color: #e5e7eb;
    font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}}

.container {{
    max-width: 1200px;
    margin: 0 auto;
}}

.header {{
    border-bottom: 1px solid #252a31;
    margin-bottom: 24px;
    padding-bottom: 16px;
}}

h1 {{
    margin: 0;
    font-size: 24px;
}}

pre {{
    margin: 0;
    padding: 20px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    background: #11151a;
    border: 1px solid #252a31;
    border-radius: 8px;
    line-height: 1.55;
}}

.meta {{
    color: #9ca3af;
    font-size: 13px;
    margin-top: 8px;
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{escaped_title}</h1>
        <div class="meta">PRALAYX investigation report</div>
    </div>
    <pre>{escaped_data}</pre>
</div>
</body>
</html>
"""

    return document.encode("utf-8")


# ---------------------------------------------------------------------------
# Report type helpers
# ---------------------------------------------------------------------------

REPORT_TYPE_DATA = {
    "actor": actor,
    "network": network,
    "full": full,
    "raw": raw,
}


def build_report_data(
    report: dict[str, Any],
    report_type: str,
) -> dict[str, Any]:
    """
    Build one logical report from a source report.
    """
    report_type = (
        str(report_type or "full")
        .strip()
        .lower()
    )

    builder = REPORT_TYPE_DATA.get(
        report_type,
        full,
    )

    return builder(report)


def build_report(
    report: dict[str, Any],
    report_type: str = "full",
    fmt: str = "json",
    title: Optional[str] = None,
) -> tuple[bytes, str, str]:
    """
    Generate report bytes.

    Returns:
        bytes
        mime_type
        file_extension
    """
    data = build_report_data(
        report,
        report_type,
    )

    fmt = (
        str(fmt or "json")
        .strip()
        .lower()
        .lstrip(".")
    )

    if title is None:
        title = (
            f"PRALAYX "
            f"{report_type.title()} Report"
        )

    if fmt == "json":
        return (
            json_bytes(data),
            "application/json",
            "json",
        )

    if fmt == "csv":
        rows = data.get("items")

        if not isinstance(rows, list):
            rows = [data]

        return (
            csv_bytes(rows),
            "text/csv",
            "csv",
        )

    if fmt in {"html", "htm"}:
        return (
            html_report(
                title,
                data,
            ),
            "text/html",
            "html",
        )

    raise ValueError(
        f"Unsupported report format: {fmt}"
    )


# ---------------------------------------------------------------------------
# Report persistence
# ---------------------------------------------------------------------------

def _safe_filename(value: str) -> str:
    value = str(value or "report")

    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "-_."
    )

    result = "".join(
        char if char in allowed else "_"
        for char in value
    )

    return result.strip("._") or "report"


def save_report(
    db: Any,
    report: dict[str, Any],
    *,
    investigation_id: str,
    report_type: str = "full",
    fmt: str = "json",
    output_dir: str | Path = "reports",
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    module_id: Optional[str] = None,
    title: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate and persist a report.

    Every call creates a new file. Existing reports are never overwritten.
    """
    output_path = Path(output_dir)

    output_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    data, mime_type, extension = build_report(
        report,
        report_type=report_type,
        fmt=fmt,
        title=title,
    )

    report_type_safe = _safe_filename(
        report_type,
    )

    investigation_safe = _safe_filename(
        investigation_id,
    )

    # Use nanosecond precision to avoid collisions during multiple reports
    # generated during the same investigation/run.
    import time

    unique_id = str(
        time.time_ns()
    )

    filename = (
        f"{investigation_safe}_"
        f"{report_type_safe}_"
        f"{unique_id}."
        f"{extension}"
    )

    path = output_path / filename

    path.write_bytes(
        data,
    )

    size = path.stat().st_size

    report_id = None

    if db is not None:
        report_id = _register_report(
            db,
            investigation_id=investigation_id,
            report_type=report_type,
            fmt=extension,
            file_name=filename,
            file_path=str(path),
            file_size=size,
            mime_type=mime_type,
            run_id=run_id,
            session_id=session_id,
            module_id=module_id,
        )

    return {
        "report_id": report_id,
        "investigation_id": investigation_id,
        "run_id": run_id,
        "session_id": session_id,
        "module_id": module_id,
        "report_type": report_type,
        "format": extension,
        "file_name": filename,
        "file_path": str(path),
        "file_size": size,
        "mime_type": mime_type,
        "status": "COMPLETED",
    }


def _register_report(
    db: Any,
    *,
    investigation_id: str,
    report_type: str,
    fmt: str,
    file_name: str,
    file_path: str,
    file_size: int,
    mime_type: str,
    run_id: Optional[str],
    session_id: Optional[str],
    module_id: Optional[str],
) -> Optional[str]:
    """
    Register the artifact in sih_reports.

    Uses the dedicated DB API when available and falls back to direct SQL
    for compatibility with an older database wrapper.
    """
    try:
        if hasattr(db, "add_report"):
            return db.add_report(
                investigation_id=investigation_id,
                run_id=run_id,
                session_id=session_id,
                module_id=module_id,
                report_type=report_type,
                format=fmt,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                status="COMPLETED",
            )
    except Exception:
        pass

    try:
        result = db.execute(
            """
            INSERT INTO sih_reports (
                investigation_id,
                session_id,
                run_id,
                module_id,
                report_type,
                format,
                file_name,
                file_path,
                file_size,
                mime_type,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                investigation_id,
                session_id,
                run_id,
                module_id,
                report_type,
                fmt,
                file_name,
                file_path,
                file_size,
                mime_type,
                "COMPLETED",
            ),
        )

        if isinstance(result, dict):
            return (
                result.get("report_id")
                or result.get("id")
            )

    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Investigation report generation
# ---------------------------------------------------------------------------

def generate_investigation_reports(
    db: Any,
    report: dict[str, Any],
    *,
    investigation_id: str,
    output_dir: str | Path = "reports",
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    module_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Generate the standard PRALAYX report set.

    JSON, HTML and CSV are retained as separate artifacts.
    """
    generated: list[dict[str, Any]] = []

    report_specs = (
        ("actor", "json"),
        ("actor", "html"),
        ("network", "json"),
        ("network", "html"),
        ("full", "json"),
        ("full", "html"),
        ("full", "csv"),
        ("raw", "json"),
    )

    for report_type, fmt in report_specs:
        try:
            generated.append(
                save_report(
                    db,
                    report,
                    investigation_id=investigation_id,
                    report_type=report_type,
                    fmt=fmt,
                    output_dir=output_dir,
                    run_id=run_id,
                    session_id=session_id,
                    module_id=module_id,
                )
            )
        except Exception as exc:
            generated.append(
                {
                    "investigation_id": investigation_id,
                    "report_type": report_type,
                    "format": fmt,
                    "status": "ERROR",
                    "error": str(exc),
                }
            )

    return generated


# ---------------------------------------------------------------------------
# Report history
# ---------------------------------------------------------------------------

def list_report_history(
    db: Any,
    investigation_id: str,
) -> list[dict[str, Any]]:
    """
    Return every report registered for an investigation.

    Nothing is collapsed or overwritten.
    """
    if db is None:
        return []

    try:
        if hasattr(
            db,
            "list_reports",
        ):
            return db.list_reports(
                investigation_id,
            )
    except Exception:
        pass

    try:
        result = db.execute(
            """
            SELECT
                report_id,
                investigation_id,
                session_id,
                run_id,
                module_id,
                report_type,
                format,
                file_name,
                file_path,
                file_size,
                mime_type,
                status,
                created_at
            FROM sih_reports
            WHERE investigation_id = ?
            ORDER BY created_at DESC
            """,
            (
                investigation_id,
            ),
        )

        return (
            result
            if isinstance(result, list)
            else []
        )

    except Exception:
        return []


def get_report(
    db: Any,
    report_id: str,
) -> Optional[dict[str, Any]]:
    """
    Fetch report metadata without deleting or modifying it.
    """
    if db is None:
        return None

    try:
        if hasattr(
            db,
            "get_report",
        ):
            return db.get_report(
                report_id,
            )
    except Exception:
        pass

    try:
        result = db.execute(
            """
            SELECT
                report_id,
                investigation_id,
                session_id,
                run_id,
                module_id,
                report_type,
                format,
                file_name,
                file_path,
                file_size,
                mime_type,
                status,
                created_at
            FROM sih_reports
            WHERE report_id = ?
            LIMIT 1
            """,
            (
                report_id,
            ),
        )

        if isinstance(result, list) and result:
            return result[0]

    except Exception:
        pass

    return None


def report_exists(
    db: Any,
    report_id: str,
) -> bool:
    return get_report(
        db,
        report_id,
    ) is not None


# ---------------------------------------------------------------------------
# Report summary
# ---------------------------------------------------------------------------

def summarize_report_history(
    reports: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """
    Produce dashboard-friendly report history statistics.
    """
    reports = list(reports or [])

    total_size = sum(
        int(
            report.get("file_size")
            or 0
        )
        for report in reports
    )

    by_type: dict[str, int] = {}
    by_format: dict[str, int] = {}

    for report in reports:
        report_type = str(
            report.get("report_type")
            or "unknown"
        )

        fmt = str(
            report.get("format")
            or "unknown"
        )

        by_type[report_type] = (
            by_type.get(report_type, 0)
            + 1
        )

        by_format[fmt] = (
            by_format.get(fmt, 0)
            + 1
        )

    return {
        "total": len(reports),
        "total_size": total_size,
        "by_type": by_type,
        "by_format": by_format,
    }


__all__ = [
    "network",
    "actor",
    "full",
    "raw",
    "json_bytes",
    "csv_bytes",
    "html_report",
    "build_report_data",
    "build_report",
    "save_report",
    "generate_investigation_reports",
    "list_report_history",
    "get_report",
    "report_exists",
    "summarize_report_history",
]
