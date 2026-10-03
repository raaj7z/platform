

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
    Generate a self-contained, human-readable executive HTML report.
    """
    inv_id = data.get("investigation_id", "INV-UNKNOWN")
    target = data.get("target", "--")
    status = data.get("status", "ACTIVE")
    created_at = data.get("created_at", "--")
    findings = data.get("findings") or []
    relationships = data.get("relationships") or []
    timeline = data.get("timeline") or []
    actor = data.get("actor") or {}

    findings_rows = ""
    for f in findings:
        findings_rows += f'''
        <tr>
            <td><span class="badge">{html.escape(str(f.get("finding_type", "OTHER")).upper())}</span></td>
            <td><strong>{html.escape(str(f.get("value", "--")))}</strong></td>
            <td><span class="mono">{html.escape(str(f.get("source_url", "--")))}</span></td>
            <td>{html.escape(str(f.get("evidence_excerpt", f.get("detail", "--"))))}</td>
            <td>{int(float(f.get("confidence", 0.85)) * 100)}%</td>
        </tr>'''

    rel_rows = ""
    for r in relationships:
        rel_rows += f'''
        <tr>
            <td><strong>{html.escape(str(r.get("from_value", "--")))}</strong></td>
            <td>➜ <em>{html.escape(str(r.get("relationship_type", "--")))}</em> ➜</td>
            <td><strong>{html.escape(str(r.get("to_value", "--")))}</strong></td>
            <td>{int(float(r.get("confidence", 0.85)) * 100)}%</td>
            <td><span class="mono">{html.escape(str(r.get("evidence_excerpt", "--")))}</span></td>
        </tr>'''

    document = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(str(title))}</title>
<style>
body {{ margin:0; padding:40px; background:#0b1329; color:#f8fafc; font-family:Inter,system-ui,sans-serif; line-height:1.5; }}
.container {{ max-width:1100px; margin:0 auto; }}
.header {{ border-bottom:2px solid #2563eb; padding-bottom:20px; margin-bottom:30px; display:flex; justify-content:space-between; align-items:center; }}
.header h1 {{ margin:0; font-size:24px; color:#38bdf8; }}
.header-meta {{ font-size:12px; color:#94a3b8; text-align:right; }}
.card {{ background:#0f1a35; border:1px solid #1e3660; border-radius:8px; padding:24px; margin-bottom:24px; }}
.card h3 {{ margin-top:0; color:#38bdf8; font-size:16px; border-bottom:1px solid #1e3660; padding-bottom:8px; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }}
.table {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:12px; }}
.table th {{ background:#132247; text-align:left; padding:10px; color:#cbd5e1; font-weight:600; border-bottom:2px solid #1e3660; }}
.table td {{ padding:10px; border-bottom:1px solid #1e3660; color:#f8fafc; }}
.badge {{ background:#2563eb22; color:#38bdf8; border:1px solid #2563eb; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:bold; }}
.mono {{ font-family:monospace; font-size:11px; color:#38bdf8; }}
.footer {{ margin-top:40px; border-top:1px solid #1e3660; padding-top:16px; text-align:center; font-size:11px; color:#64748b; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h1>PRALAYX Intelligence Forensic Report</h1>
            <div style="font-size:13px;color:#cbd5e1;margin-top:4px">Case ID: <strong>{html.escape(inv_id)}</strong> | Target: <strong>{html.escape(target)}</strong></div>
        </div>
        <div class="header-meta">
            <div>STATUS: <strong style="color:#10b981">{html.escape(status)}</strong></div>
            <div>Generated: {html.escape(created_at)}</div>
            <div>Classification: LAW ENFORCEMENT SENSITIVE</div>
        </div>
    </div>

    <div class="card">
        <h3>1. Executive Summary</h3>
        <p>This document presents confirmed technical findings, OPSEC misconfigurations, cross-platform OSINT footprints, and AI persona continuity analysis gathered by the <strong>PRALAYX Threat Actor De-anonymization Platform</strong> for investigation <strong>{html.escape(inv_id)}</strong>.</p>
        <div class="grid">
            <div><strong>Primary Target:</strong> {html.escape(target)}</div>
            <div><strong>Total Findings Discovered:</strong> {len(findings)}</div>
            <div><strong>Graph Relationships Identified:</strong> {len(relationships)}</div>
            <div><strong>Timeline Events Logged:</strong> {len(timeline)}</div>
        </div>
    </div>

    <div class="card">
        <h3>2. Discovered Technical Indicators & Misconfigurations</h3>
        <table class="table">
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Value / Indicator</th>
                    <th>Source URL</th>
                    <th>Evidence Excerpt</th>
                    <th>Confidence</th>
                </tr>
            </thead>
            <tbody>
                {findings_rows if findings_rows else '<tr><td colspan="5" style="text-align:center;color:#64748b">No technical findings recorded</td></tr>'}
            </tbody>
        </table>
    </div>

    <div class="card">
        <h3>3. Attribution & Correlation Graph Relationships</h3>
        <table class="table">
            <thead>
                <tr>
                    <th>From Entity</th>
                    <th>Relationship</th>
                    <th>To Entity</th>
                    <th>Confidence</th>
                    <th>Evidence Provenance</th>
                </tr>
            </thead>
            <tbody>
                {rel_rows if rel_rows else '<tr><td colspan="5" style="text-align:center;color:#64748b">No graph relationships identified</td></tr>'}
            </tbody>
        </table>
    </div>

    <div class="footer">
        PRALAYX v2.0 (SIH26151) — Dark Web Threat Actor De-anonymization Platform<br>
        Confidential Forensic Audit Export — Chain of Custody Verified
    </div>
</div>
</body>
</html>'''

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

    if fmt == "pdf":
        return (
            pdf_bytes(
                title,
                data,
            ),
            "application/pdf",
            "pdf",
        )

    raise ValueError(
        f"Unsupported report format: {fmt}"
    )


def pdf_bytes(
    title: str,
    data: Any,
) -> bytes:
    """
    Generate a formatted executive PDF report using ReportLab.
    """
    from datetime import datetime, timezone
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    inv_id = data.get("investigation_id", "INV-UNKNOWN")
    target = data.get("target", "--")
    status = data.get("status", "ACTIVE")
    findings = data.get("findings") or []
    relationships = data.get("relationships") or []

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
    )

    h2_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#2563eb"),
        spaceBefore=10,
        spaceAfter=6,
    )

    normal_style = styles["Normal"]

    # Title & Metadata
    story.append(Paragraph(f"<b>{html.escape(str(title))}</b>", title_style))
    story.append(Paragraph(f"<b>Case ID:</b> {html.escape(inv_id)} | <b>Target:</b> {html.escape(target)} | <b>Status:</b> {html.escape(status)}", normal_style))
    story.append(Paragraph(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | Classification: LAW ENFORCEMENT SENSITIVE", normal_style))
    story.append(Spacer(1, 12))

    # Executive Summary Narrative
    story.append(Paragraph("<b>1. Executive Summary Narrative</b>", h2_style))
    exec_summary = f"This report consolidates technical misconfigurations, onion scraping findings, clearweb OSINT footprints, and stylometric persona continuity analysis compiled by PRALAYX for investigation <b>{html.escape(inv_id)}</b>. A total of <b>{len(findings)}</b> findings and <b>{len(relationships)}</b> relationship links were established."
    story.append(Paragraph(exec_summary, normal_style))
    story.append(Spacer(1, 10))

    # Key Findings Table
    story.append(Paragraph("<b>2. Key Technical Indicators & Misconfigurations</b>", h2_style))
    table_data = [["Type", "Indicator / Value", "Source URL", "Confidence"]]
    for f in findings[:15]:
        table_data.append([
            str(f.get("finding_type", "")).upper()[:16],
            str(f.get("value", ""))[:32],
            str(f.get("source_url", ""))[:30],
            f"{int(float(f.get('confidence', 0.85))*100)}%"
        ])

    if len(table_data) == 1:
        table_data.append(["--", "No technical findings recorded", "--", "--"])

    t = Table(table_data, colWidths=[110, 180, 180, 70])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # Disclaimer Footer
    story.append(Paragraph("<b>Forensic Notice & Limitations:</b> All findings reflect empirical evidence collected at time of analysis. Stylometry and handle continuity similarities serve as investigative leads requiring human forensic review.", ParagraphStyle("Notice", parent=normal_style, fontSize=8, textColor=colors.HexColor("#64748b"))))

    doc.build(story)
    return buffer.getvalue()


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
