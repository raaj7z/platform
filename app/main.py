from __future__ import annotations

import asyncio
import datetime
import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analysis import (
    analyze_posts,
    compare_personas,
    persist_analysis,
)
from .config import (
    CRAWLER_PATH,
    DB_PATH,
    REPORTS_PATH,
    SCHEMA_PATH,
    WEB_PATH,
)
from .crawler_runner import (
    run as run_crawler,
)
from .database import DB
from .engine_runner import (
    run_osint,
    run_osint_from_crawl,
)
from .reports import (
    actor,
    build_report,
    csv_bytes,
    generate_investigation_reports,
    get_report,
    html_report,
    list_report_history,
    network,
    save_report,
    summarize_report_history,
)
from .tracking import (
    Scheduler,
    WatchlistManager,
)


# ============================================================
# DATABASE
# ============================================================

db = DB(DB_PATH)

if Path(SCHEMA_PATH).exists():
    db.migrate(SCHEMA_PATH)
else:
    raise RuntimeError(
        f"Shared schema not found: {SCHEMA_PATH}"
    )


# ============================================================
# GLOBAL STATE
# ============================================================

scheduler: Scheduler | None = None


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Start long-lived PRALAYX resources before requests begin
    and release them during shutdown.
    """
    global scheduler

    try:
        scheduler = Scheduler(
            db=db,
            callback=_scheduled_scan,
            tick_seconds=15,
        )

        scheduler.start()

    except Exception:
        scheduler = None

    yield

    if scheduler is not None:
        try:
            scheduler.stop()
        except Exception:
            pass

        scheduler = None

    try:
        db.close()
    except Exception:
        pass


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="PRALAYX",
    description=(
        "SIH26151 Dark Web Threat Actor "
        "Intelligence and De-anonymization Platform"
    ),
    version="2.0.0",
    lifespan=lifespan,
)
app.mount(
    "/web",
    StaticFiles(directory=WEB_PATH),
    name="web",
)


# ============================================================
# REQUEST MODELS
# ============================================================

class Crawl(BaseModel):
    urls: list[str] = Field(
        min_length=1,
    )

    target: str | None = None

    workers: int = Field(
        default=3,
        ge=1,
        le=10,
    )


class Investigate(BaseModel):
    target: str

    target_type: str = "other"

    notes: str | None = None


class Watch(BaseModel):
    actor_id: str

    interval_minutes: int = Field(
        default=60,
        ge=5,
    )


class Persona(BaseModel):
    posts: list[dict[str, Any]]


class ComparePersona(BaseModel):
    persona_a: dict[str, Any]
    persona_b: dict[str, Any]


class GenerateReports(BaseModel):
    formats: list[str] = Field(
        default_factory=lambda: [
            "json",
            "html",
        ]
    )


# ============================================================
# DATABASE COMPATIBILITY HELPERS
# ============================================================

def _db_call(
    method: str,
    *args,
    **kwargs,
):
    """
    Call a database method when available.

    This keeps the API layer tolerant of small differences between
    database implementations while the unified schema is being adopted.
    """
    fn = getattr(
        db,
        method,
        None,
    )

    if not callable(fn):
        return None

    return fn(
        *args,
        **kwargs,
    )


def _investigation(
    investigation_id: str,
):
    return _db_call(
        "investigation",
        investigation_id,
    ) or _db_call(
        "get_investigation",
        investigation_id,
    )


def _investigations():
    return _db_call(
        "investigations",
    ) or _db_call(
        "list_investigations",
    ) or []


def _job(
    job_id: str,
):
    return _db_call(
        "job",
        job_id,
    ) or _db_call(
        "get_job",
        job_id,
    )


def _events(
    job_id: str,
):
    return _db_call(
        "events",
        job_id,
    ) or _db_call(
        "get_job_events",
        job_id,
    ) or []


def _reports(
    investigation_id: str,
):
    return list_report_history(
        db,
        investigation_id,
    )


# ============================================================
# SCHEDULED MONITORING CALLBACK
# ============================================================

def _scheduled_scan(
    watch: dict[str, Any],
):
    """
    Callback used by the monitoring scheduler.

    A watchlist item identifies an actor. The scan creates a new
    investigation/run rather than mutating an older report.

    Actual provider/crawler execution can therefore produce another
    independent report track.
    """
    actor_id = watch.get(
        "actor_id"
    )

    if not actor_id:
        return {
            "status": "ERROR",
            "error": "watchlist item has no actor_id",
        }

    actor_data = _db_call(
        "get_actor",
        actor_id,
    )

    if not actor_data:
        return {
            "status": "ERROR",
            "error": (
                f"actor not found: {actor_id}"
            ),
        }

    target = (
        actor_data.get("primary_identifier")
        or actor_data.get("name")
        or actor_data.get("username")
    )

    if not target:
        return {
            "status": "ERROR",
            "error": (
                "tracked actor has no usable "
                "identifier"
            ),
        }

    target_type = (
        actor_data.get("primary_type")
        or "username"
    )

    investigation_id, linked_actor_id = (
        db.create_investigation(
            target,
            target_type,
            "monitoring",
        )
    )

    job_id = db.create_job(
        investigation_id=investigation_id,
        job_type="scheduled_osint",
        payload={
            "actor_id": actor_id,
            "target": target,
            "target_type": target_type,
            "watch_id": watch.get(
                "watch_id"
            ),
        },
    )

    thread = threading.Thread(
        target=run_osint,
        kwargs={
            "db": db,
            "job_id": job_id,
            "iid": investigation_id,
            "actor_id": (
                linked_actor_id
                or actor_id
            ),
            "target": target,
            "target_type": target_type,
        },
        daemon=True,
    )

    thread.start()

    return {
        "status": "RUNNING",
        "job_id": job_id,
        "investigation_id": investigation_id,
        "actor_id": (
            linked_actor_id
            or actor_id
        ),
    }


# ============================================================
# HOME
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def home():
    html_path = (
        Path(WEB_PATH)
        / "index.html"
    )

    if not html_path.exists():
        raise HTTPException(
            status_code=500,
            detail="web/index.html not found",
        )

    return html_path.read_text(
        encoding="utf-8",
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "platform": "PRALAYX",
        "version": "2.0.0",
        "database": str(DB_PATH),
        "schema": str(SCHEMA_PATH),
        "crawler_path": str(CRAWLER_PATH),
        "reports_path": str(REPORTS_PATH),
        "scheduler": (
            scheduler.running()
            if scheduler
            else False
        ),
    }


# ============================================================
# CRAWLER
# ============================================================

@app.post("/api/crawl")
def crawl(
    request: Crawl,
):
    target = (
        request.target
        or request.urls[0]
    )

    target_type = (
        "username"
        if request.target
        else "url"
    )

    investigation_id, actor_id = (
        db.create_investigation(
            target,
            target_type,
            "crawler",
        )
    )

    job_id = db.create_job(
        investigation_id=investigation_id,
        job_type="crawl",
        payload=request.model_dump(),
    )

    thread = threading.Thread(
        target=run_crawler,
        kwargs={
            "db": db,
            "job_id": job_id,
            "investigation_id": investigation_id,
            "actor_id": actor_id,
            "urls": request.urls,
            "target": request.target,
            "workers": request.workers,
        },
        daemon=True,
    )

    thread.start()

    return {
        "job_id": job_id,
        "investigation_id": investigation_id,
        "actor_id": actor_id,
        "status": "RUNNING",
    }


# ============================================================
# MANUAL OSINT
# ============================================================

@app.post("/api/investigate")
def investigate(
    request: Investigate,
):
    investigation_id, actor_id = (
        db.create_investigation(
            request.target,
            request.target_type,
            "manual",
            request.notes,
        )
    )

    job_id = db.create_job(
        investigation_id=investigation_id,
        job_type="osint",
        payload=request.model_dump(),
    )

    thread = threading.Thread(
        target=run_osint,
        kwargs={
            "db": db,
            "job_id": job_id,
            "iid": investigation_id,
            "actor_id": actor_id,
            "target": request.target,
            "target_type": request.target_type,
        },
        daemon=True,
    )

    thread.start()

    return {
        "job_id": job_id,
        "investigation_id": investigation_id,
        "actor_id": actor_id,
        "status": "RUNNING",
    }


# ============================================================
# SEND CRAWLER FINDINGS TO OSINT
# ============================================================

@app.post(
    "/api/investigations/{investigation_id}/send-to-osint",
)
def send_to_osint(
    investigation_id: str,
):
    investigation_data = _investigation(
        investigation_id,
    )

    if not investigation_data:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    findings = investigation_data.get(
        "findings",
        [],
    )

    if not findings:
        raise HTTPException(
            status_code=400,
            detail=(
                "No crawler findings are "
                "available for this investigation."
            ),
        )

    supported_types = {
        "username",
        "email",
        "url",
        "domain",
        "dns",
        "ip",
        "pgp",
        "crypto",
    }

    identifiers = []
    seen = set()

    for finding in findings:
        finding_type = (
            finding.get("finding_type")
            or finding.get("type")
            or "other"
        )

        value = (
            finding.get("value")
            or finding.get("normalized_value")
        )

        if not value:
            continue

        finding_type = str(
            finding_type
        ).lower()

        if finding_type not in supported_types:
            continue

        key = (
            finding_type,
            str(value).strip().lower(),
        )

        if key in seen:
            continue

        seen.add(key)

        identifiers.append(
            {
                "type": finding_type,
                "value": str(value),
                "source": (
                    finding.get("source")
                    or "dark-crawler"
                ),
                "source_url": finding.get(
                    "source_url"
                ),
                "confidence": finding.get(
                    "confidence",
                    0.5,
                ),
            }
        )

    if not identifiers:
        raise HTTPException(
            status_code=400,
            detail=(
                "No supported OSINT identifiers "
                "were found in the crawler report."
            ),
        )

    actor_id = investigation_data.get(
        "actor_id"
    )

    job_id = db.create_job(
        "osint_from_crawler",
        investigation_id,
        {
            "investigation_id": investigation_id,
            "actor_id": actor_id,
            "identifier_count": len(
                identifiers
            ),
        },
    )

    thread = threading.Thread(
        target=run_osint_from_crawl,
        kwargs={
            "db": db,
            "job_id": job_id,
            "iid": investigation_id,
            "actor_id": actor_id,
            "identifiers": identifiers,
        },
        daemon=True,
    )

    thread.start()

    return {
        "job_id": job_id,
        "investigation_id": investigation_id,
        "actor_id": actor_id,
        "identifier_count": len(
            identifiers
        ),
        "status": "RUNNING",
    }


# ============================================================
# JOBS
# ============================================================

@app.get("/api/jobs")
def list_jobs(status: Optional[str] = None, investigation_id: Optional[str] = None):
    try:
        with db.connect() as conn:
            query = "SELECT * FROM sih_jobs"
            params = []
            conditions = []
            if status:
                conditions.append("LOWER(status) = ?")
                params.append(status.lower())
            if investigation_id:
                conditions.append("investigation_id = ?")
                params.append(investigation_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT 50"
            rows = conn.execute(query, params).fetchall()
            jobs = []
            now = datetime.datetime.now(datetime.timezone.utc)
            for r in rows:
                j = dict(r)
                payload = {}
                if j.get("payload"):
                    try:
                        payload = json.loads(j["payload"])
                    except Exception:
                        pass
                j["payload_parsed"] = payload
                j["target"] = (
                    payload.get("target")
                    or (payload.get("urls")[0] if isinstance(payload.get("urls"), list) and payload.get("urls") else None)
                    or j.get("investigation_id")
                )
                j_type = str(j.get("job_type", "")).lower()
                if "osint" in j_type:
                    j["process_name"] = "OSINT De-anonymization & Footprinting Engine"
                elif "crawl" in j_type:
                    j["process_name"] = "DarkWeb & Surface Web Crawler Engine"
                else:
                    j["process_name"] = f"{j_type.upper()} Execution Engine"

                created_str = j.get("created_at")
                elapsed_sec = 0
                if created_str:
                    try:
                        dt = datetime.datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                        elapsed_sec = max(0, int((now - dt).total_seconds()))
                    except Exception:
                        pass
                j["elapsed_seconds"] = elapsed_sec

                prog = float(j.get("progress") or 0.0)
                if prog >= 1.0 or str(j.get("status")).lower() in ("completed", "failed", "no_results"):
                    est_rem = 0
                elif prog > 0.05:
                    est_total = elapsed_sec / prog
                    est_rem = max(1, int(est_total - elapsed_sec))
                else:
                    est_rem = max(1, 35 - elapsed_sec) if "osint" in j_type else max(1, 45 - elapsed_sec)

                j["estimated_seconds_remaining"] = est_rem

                latest_evt = conn.execute(
                    "SELECT message FROM sih_job_events WHERE job_id = ? ORDER BY created_at DESC LIMIT 1",
                    (j["job_id"],)
                ).fetchone()
                j["latest_event"] = latest_evt["message"] if latest_evt else "Running process..."
                jobs.append(j)
            return {"status": "ok", "jobs": jobs, "total": len(jobs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jobs: {e}")

@app.get("/api/jobs/{job_id}")
def get_job(
    job_id: str,
):
    job = _job(
        job_id,
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="job not found",
        )

    evts = _events(job_id)
    j = dict(job)
    now = datetime.datetime.now(datetime.timezone.utc)
    created_str = j.get("created_at")
    elapsed_sec = 0
    if created_str:
        try:
            dt = datetime.datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            elapsed_sec = max(0, int((now - dt).total_seconds()))
        except Exception:
            pass
    j["elapsed_seconds"] = elapsed_sec
    j_type = str(j.get("job_type", "")).lower()
    if "osint" in j_type:
        j["process_name"] = "OSINT De-anonymization & Footprinting Engine"
    elif "crawl" in j_type:
        j["process_name"] = "DarkWeb & Surface Web Crawler Engine"
    else:
        j["process_name"] = f"{j_type.upper()} Execution Engine"

    prog = float(j.get("progress") or 0.0)
    if prog >= 1.0 or str(j.get("status")).lower() in ("completed", "failed", "no_results"):
        est_rem = 0
    elif prog > 0.05:
        est_total = elapsed_sec / prog
        est_rem = max(1, int(est_total - elapsed_sec))
    else:
        est_rem = max(1, 35 - elapsed_sec) if "osint" in j_type else max(1, 45 - elapsed_sec)

    j["estimated_seconds_remaining"] = est_rem

    return {
        "job": j,
        "events": evts,
    }


# ============================================================
# LIVE TERMINAL WEBSOCKET
# ============================================================

@app.websocket(
    "/ws/jobs/{job_id}",
)
async def websocket_job(
    websocket: WebSocket,
    job_id: str,
):
    await websocket.accept()

    sent: set[str] = set()

    try:
        while True:
            job = _job(
                job_id,
            )

            if not job:
                await websocket.send_json(
                    {
                        "event_type": "ERROR",
                        "message": "job not found",
                    }
                )
                return

            events = _events(
                job_id,
            )

            for event in events:
                event_id = str(
                    event.get(
                        "event_id"
                    )
                    or event.get("id")
                    or ""
                )

                if event_id and event_id in sent:
                    continue

                if event_id:
                    sent.add(
                        event_id
                    )

                payload = event.get(
                    "payload"
                )

                if isinstance(
                    payload,
                    str,
                ):
                    try:
                        event["payload"] = json.loads(
                            payload
                        )
                    except Exception:
                        pass

                await websocket.send_json(
                    event
                )

            status = str(
                job.get("status")
                or ""
            ).upper()

            if status in {
                "COMPLETED",
                "FAILED",
                "ERROR",
                "TIMEOUT",
                "NO_RESULTS",
                "CANCELLED",
            }:
                await websocket.send_json(
                    {
                        "event_type": "TERMINAL",
                        "message": (
                            f"Job {status}"
                        ),
                        "status": status,
                    }
                )
                return

            await asyncio.sleep(
                0.8
            )

    except WebSocketDisconnect:
        return


# ============================================================
# INVESTIGATIONS
# ============================================================

@app.get("/api/investigations")
def investigations():
    return _investigations()


@app.get(
    "/api/investigations/{investigation_id}",
)
def investigation(
    investigation_id: str,
):
    result = _investigation(
        investigation_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    return result


# ============================================================
# INVESTIGATION TIMELINE
# ============================================================

@app.get(
    "/api/investigations/{investigation_id}/timeline",
)
def investigation_timeline(
    investigation_id: str,
):
    if not _investigation(
        investigation_id,
    ):
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    result = _db_call(
        "timeline",
        investigation_id,
    )

    if result is None:
        result = _db_call(
            "get_timeline",
            investigation_id,
        )

    return result or []


# ============================================================
# REPORT HISTORY
# ============================================================

@app.get(
    "/api/investigations/{investigation_id}/reports",
)
def investigation_reports(
    investigation_id: str,
):
    if not _investigation(
        investigation_id,
    ):
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    reports = _reports(
        investigation_id,
    )

    return {
        "investigation_id": investigation_id,
        "reports": reports,
        "summary": summarize_report_history(
            reports,
        ),
    }


@app.get(
    "/api/reports/{report_id}",
)
def report_metadata(
    report_id: str,
):
    result = get_report(
        db,
        report_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="report not found",
        )

    return result


@app.get(
    "/api/reports/{report_id}/file",
)
def report_file(
    report_id: str,
):
    result = get_report(
        db,
        report_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="report not found",
        )

    path = Path(
        result.get(
            "file_path",
            "",
        )
    ).resolve()

    reports_root = Path(
        REPORTS_PATH
    ).resolve()

    try:
        path.relative_to(
            reports_root
        )
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="invalid report path",
        )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="report file no longer exists",
        )

    return FileResponse(
        path,
        media_type=(
            result.get(
                "mime_type"
            )
            or "application/octet-stream"
        ),
        filename=(
            result.get(
                "file_name"
            )
            or path.name
        ),
    )


# ============================================================
# GENERATE REPORT SET
# ============================================================

@app.post(
    "/api/investigations/{investigation_id}/reports/generate",
)
def generate_reports(
    investigation_id: str,
    request: GenerateReports,
):
    investigation_data = _investigation(
        investigation_id,
    )

    if not investigation_data:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    generated = []

    requested_formats = {
        str(fmt).lower().lstrip(".")
        for fmt in request.formats
    }

    supported_formats = {
        "json",
        "html",
        "csv",
    }

    requested_formats &= supported_formats

    if not requested_formats:
        requested_formats = {
            "json",
            "html",
        }

    for fmt in sorted(
        requested_formats
    ):
        for report_type in (
            "actor",
            "network",
            "full",
            "raw",
        ):
            try:
                generated.append(
                    save_report(
                        db,
                        investigation_data,
                        investigation_id=(
                            investigation_id
                        ),
                        report_type=report_type,
                        fmt=fmt,
                        output_dir=(
                            REPORTS_PATH
                        ),
                    )
                )
            except Exception as exc:
                generated.append(
                    {
                        "investigation_id": (
                            investigation_id
                        ),
                        "report_type": report_type,
                        "format": fmt,
                        "status": "ERROR",
                        "error": str(exc),
                    }
                )

    return {
        "investigation_id": investigation_id,
        "reports": generated,
        "count": len(generated),
    }


# ============================================================
# CRAWLER REPORTS
# ============================================================

CRAWLER_REPORTS = {
    "actor_report.json",
    "network_report.json",
    "actor.json",
    "network.json",
    "actor.csv",
    "network.csv",
    "actor.jsonl",
    "network.jsonl",
}


def _crawler_report_path(
    investigation_id: str,
    report_name: str,
):
    if report_name not in CRAWLER_REPORTS:
        raise HTTPException(
            status_code=400,
            detail="unsupported crawler report",
        )

    investigation_data = _investigation(
        investigation_id,
    )

    if not investigation_data:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    crawler_session_id = (
        investigation_data.get(
            "crawler_session_id"
        )
    )

    if not crawler_session_id:
        raise HTTPException(
            status_code=404,
            detail="crawler report not available yet",
        )

    crawler_root = Path(
        CRAWLER_PATH
    ).resolve()

    report_root = (
        crawler_root
        / "output"
        / f"session_{crawler_session_id}"
    ).resolve()

    report_path = (
        report_root
        / report_name
    ).resolve()

    try:
        report_path.relative_to(
            report_root
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="invalid report path",
        )

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"crawler report not found: "
                f"{report_name}"
            ),
        )

    if not report_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="crawler report is not a file",
        )

    return report_path


@app.get(
    "/api/reports/{investigation_id}/crawler/{report_name}",
)
def crawler_report(
    investigation_id: str,
    report_name: str,
):
    path = _crawler_report_path(
        investigation_id,
        report_name,
    )

    if path.suffix == ".csv":
        media_type = "text/csv"
    elif path.suffix == ".jsonl":
        media_type = "application/x-ndjson"
    else:
        media_type = "application/json"

    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
    )


# ============================================================
# REPORT TYPE VIEWS
# ============================================================

@app.get(
    "/api/reports/{investigation_id}/network",
)
def network_report(
    investigation_id: str,
):
    result = _investigation(
        investigation_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    return network(
        result,
    )


@app.get(
    "/api/reports/{investigation_id}/threat-actor",
)
def actor_report(
    investigation_id: str,
):
    result = _investigation(
        investigation_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    return actor(
        result,
    )


# ============================================================
# FINDINGS
# ============================================================

@app.get("/api/findings")
def findings(
    actor: str | None = None,
    finding_type: str | None = None,
    confidence: float | None = Query(
        default=None,
        ge=0,
        le=1,
    ),
    q: str | None = None,
):
    result = _db_call(
        "filtered_findings",
        actor=actor,
        ftype=finding_type,
        confidence=confidence,
        q=q,
    )

    return result or []


# ============================================================
# PERSONA / STYLOMETRY
# ============================================================

@app.post("/api/persona/analyze")
def persona(
    request: Persona,
):
    result = analyze_posts(
        request.posts,
    )

    return result


@app.post("/api/persona/compare")
def persona_compare(
    request: ComparePersona,
):
    return compare_personas(
        request.persona_a,
        request.persona_b,
    )


@app.post(
    "/api/investigations/{investigation_id}/persona/analyze",
)
def investigation_persona(
    investigation_id: str,
    request: Persona,
):
    investigation_data = _investigation(
        investigation_id,
    )

    if not investigation_data:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    actor_id = investigation_data.get(
        "actor_id"
    )

    result = persist_analysis(
        db,
        investigation_id,
        request.posts,
        actor_id=actor_id,
    )

    return result


# ============================================================
# EXPORTS
# ============================================================

@app.get(
    "/api/export/{investigation_id}/json",
)
def export_json(
    investigation_id: str,
):
    result = _investigation(
        investigation_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    return Response(
        content=json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{investigation_id}.json"'
            )
        },
    )


@app.get(
    "/api/export/{investigation_id}/csv",
)
def export_csv(
    investigation_id: str,
):
    result = _investigation(
        investigation_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    return Response(
        content=csv_bytes(
            result.get(
                "findings",
                [],
            )
        ),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{investigation_id}.csv"'
            )
        },
    )


@app.get(
    "/api/export/{investigation_id}/html",
)
def export_html(
    investigation_id: str,
):
    result = _investigation(
        investigation_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    return Response(
        content=html_report(
            "PRALAYX Investigation",
            result,
        ),
        media_type="text/html",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{investigation_id}.html"'
            )
        },
    )


@app.get(
    "/api/export/{investigation_id}/pdf",
)
def export_pdf(
    investigation_id: str,
):
    result = _investigation(
        investigation_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    data, mime_type, extension = build_report(
        result,
        report_type="full",
        fmt="pdf",
        title=f"PRALAYX Investigation {investigation_id}",
    )

    return Response(
        content=data,
        media_type=mime_type,
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{investigation_id}.pdf"'
            )
        },
    )


@app.get("/api/persona/synthetic-demo")
def persona_synthetic_demo():
    from .persona_adapter import get_synthetic_rebrand_demo
    return get_synthetic_rebrand_demo()


@app.post("/api/investigations/{investigation_id}/correlate")
def correlate_investigation(investigation_id: str):
    inv = _investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="investigation not found")
    _db_call("correlate_investigation", investigation_id)
    return _investigation(investigation_id)


@app.get("/api/investigations/{investigation_id}/misconfigurations")
def misconfigurations_report(investigation_id: str):
    inv = _investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="investigation not found")

    findings = inv.get("findings", [])
    categories = {
        "server_status": [],
        "tls_certificates": [],
        "service_banners": [],
        "descriptor_inconsistencies": [],
        "other": []
    }

    for f in findings:
        ftype = str(f.get("finding_type", "")).lower()
        val = str(f.get("value", "")).lower()
        if "server-status" in ftype or "server_status" in val or "phpinfo" in val or ".git" in val:
            categories["server_status"].append(f)
        elif "tls" in ftype or "ssl" in ftype or "certificate" in ftype or "cert" in val:
            categories["tls_certificates"].append(f)
        elif "banner" in ftype or "banner" in val or "ssh" in val or "apache" in val or "nginx" in val:
            categories["service_banners"].append(f)
        elif "descriptor" in ftype or "leak" in val or "clearnet" in val:
            categories["descriptor_inconsistencies"].append(f)
        else:
            categories["other"].append(f)

    return {
        "investigation_id": investigation_id,
        "categories": categories,
        "total_misconfigurations": sum(len(v) for v in categories.values()),
    }


# ============================================================
# WATCHLIST
# ============================================================

@app.post("/api/watchlist")
def add_watch(
    request: Watch,
):
    manager = WatchlistManager(
        db,
    )

    watch_id = manager.add(
        request.actor_id,
        request.interval_minutes,
    )

    return {
        "watch_id": watch_id,
        "actor_id": request.actor_id,
        "interval_minutes": (
            request.interval_minutes
        ),
        "status": "ACTIVE",
    }


@app.get("/api/watchlist")
def watchlist():
    manager = WatchlistManager(
        db,
    )

    return manager.list()


@app.post(
    "/api/watchlist/{watch_id}/pause",
)
def pause_watch(
    watch_id: str,
):
    manager = WatchlistManager(
        db,
    )

    manager.pause(
        watch_id,
    )

    return {
        "watch_id": watch_id,
        "status": "PAUSED",
    }


@app.post(
    "/api/watchlist/{watch_id}/resume",
)
def resume_watch(
    watch_id: str,
):
    manager = WatchlistManager(
        db,
    )

    manager.resume(
        watch_id,
    )

    return {
        "watch_id": watch_id,
        "status": "ACTIVE",
    }


@app.delete(
    "/api/watchlist/{watch_id}",
)
def delete_watch(
    watch_id: str,
):
    manager = WatchlistManager(
        db,
    )

    manager.remove(
        watch_id,
    )

    return {
        "watch_id": watch_id,
        "status": "REMOVED",
    }


# ============================================================
# ALERTS
# ============================================================

@app.get("/api/alerts")
def alerts(
    unread: bool = False,
):
    result = _db_call(
        "alerts",
        unread,
    )

    return result or []


@app.post(
    "/api/alerts/{alert_id}/read",
)
def read_alert(
    alert_id: str,
):
    _db_call(
        "mark_alert",
        alert_id,
    )

    return {
        "ok": True,
        "alert_id": alert_id,
    }


# ============================================================
# TERMINAL HISTORY
# ============================================================

@app.get(
    "/api/investigations/{investigation_id}/terminal",
)
def terminal_history(
    investigation_id: str,
):
    """
    Return all terminal/job events belonging to the investigation.
    """
    investigation_data = _investigation(
        investigation_id,
    )

    if not investigation_data:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    sessions = _db_call(
        "list_sessions",
        investigation_id,
    ) or []

    result = []

    for session in sessions:
        session_id = (
            session.get("session_id")
            or session.get("id")
        )

        if not session_id:
            continue

        jobs = _db_call(
            "list_jobs",
            session_id=session_id,
        ) or []

        for job in jobs:
            job_id = (
                job.get("job_id")
                or job.get("id")
            )

            if not job_id:
                continue

            result.append(
                {
                    "job": job,
                    "events": _events(
                        job_id,
                    ),
                }
            )

    return {
        "investigation_id": investigation_id,
        "sessions": result,
    }


# ============================================================
# SYSTEM SETTINGS & MAINTENANCE
# ============================================================

SETTINGS_FILE = Path(DB_PATH).parent / "settings.json"

class SystemSettings(BaseModel):
    tor_host: str = "127.0.0.1"
    tor_port: int = 9050
    require_tor_for_onion: bool = True
    shodan_api_key: str | None = ""
    virustotal_api_key: str | None = ""
    alienvault_api_key: str | None = ""
    default_workers: int = 3
    crawl_timeout_seconds: int = 120

def _load_settings_json() -> dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "tor_host": "127.0.0.1",
        "tor_port": 9050,
        "require_tor_for_onion": True,
        "shodan_api_key": "",
        "virustotal_api_key": "",
        "alienvault_api_key": "",
        "default_workers": 3,
        "crawl_timeout_seconds": 120,
    }

@app.get("/api/settings")
def get_settings():
    s = _load_settings_json()
    s["shodan_configured"] = bool(s.get("shodan_api_key"))
    s["virustotal_configured"] = bool(s.get("virustotal_api_key"))
    s["alienvault_configured"] = bool(s.get("alienvault_api_key"))
    db_p = Path(DB_PATH)
    s["database_path"] = str(db_p)
    s["database_size_bytes"] = db_p.stat().st_size if db_p.exists() else 0
    return s

@app.post("/api/settings")
def update_settings(req: SystemSettings):
    data = req.model_dump()
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"status": "ok", "message": "System configuration updated successfully", "settings": data}

@app.post("/api/settings/test-tor")
def test_tor():
    import socket
    s = _load_settings_json()
    host = s.get("tor_host", "127.0.0.1")
    port = int(s.get("tor_port", 9050))
    ok = False
    msg = ""
    try:
        with socket.create_connection((host, port), timeout=3.0):
            ok = True
            msg = f"Tor SOCKS proxy active and listening on {host}:{port}"
    except Exception as e:
        ok = False
        msg = f"Tor SOCKS proxy not reachable at {host}:{port} ({e})"

    return {"ok": ok, "status": "ONLINE" if ok else "OFFLINE", "message": msg, "host": host, "port": port}

@app.post("/api/settings/vacuum-db")
def vacuum_db():
    try:
        with db.connect() as conn:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
            conn.commit()
        db_p = Path(DB_PATH)
        size = db_p.stat().st_size if db_p.exists() else 0
        return {"status": "ok", "message": "Database optimized successfully", "size_bytes": size}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database optimization failed: {e}")

@app.post("/api/history/clear")
def clear_history():
    tables = [
        "sih_reports",
        "sih_raw_snapshots",
        "sih_job_events",
        "sih_jobs",
        "sih_investigation_timeline",
        "sih_relationships",
        "sih_entity_sightings",
        "sih_observations",
        "sih_evidence",
        "sih_findings",
        "sih_identifiers",
        "sih_runs",
        "sih_sessions",
        "sih_watchlist",
        "sih_alerts",
        "sih_investigations",
        "sih_actors",
    ]
    try:
        with db.connect() as conn:
            for t in tables:
                try:
                    conn.execute(f"DELETE FROM {t}")
                except Exception:
                    pass
            conn.commit()
            try:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                conn.commit()
            except Exception:
                pass

        try:
            from .seed_demo import seed
            seed()
        except Exception:
            pass

        return {"status": "ok", "message": "Search, crawl history, and database records cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clear history failed: {e}")

# ============================================================
# RUN SERVER
# ============================================================

__all__ = [
    "app",
    "db",
]
