from __future__ import annotations

import asyncio
import datetime
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Any

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
    VERCEL_DEMO_MODE,
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

if VERCEL_DEMO_MODE:
    try:
        from .vercel_demo import initialize_vercel_demo

        initialize_vercel_demo()
    except Exception as exc:
        print(
            f"PRALAYX Vercel demo initialization failed: {exc}"
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

    if not VERCEL_DEMO_MODE:
        try:
            scheduler = Scheduler(
                db=db,
                callback=_scheduled_scan,
                tick_seconds=15,
            )

            scheduler.start()

        except Exception:
            scheduler = None
    else:
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

def run_monitoring_scan(db: DB, watch: dict[str, Any]):
    """
    Execute a monitoring crawl scan reusing the existing crawler.
    Performs snapshot diff comparison, change detection, timeline logging, and alert generation.
    """
    watch_id = watch.get("watch_id")
    target = watch.get("target") or watch.get("target_display")
    investigation_id = watch.get("investigation_id")
    actor_id = watch.get("actor_id")

    if not target and actor_id:
        actor_data = _db_call("get_actor", actor_id)
        if actor_data:
            target = actor_data.get("display_name") or actor_data.get("primary_identifier")

    if not target:
        return {"status": "ERROR", "error": "Watchlist item has no target"}

    if not investigation_id:
        investigation_id, linked_actor_id = db.create_investigation(
            target, "onion" if ".onion" in target else "url", "monitoring"
        )
        actor_id = actor_id or linked_actor_id

    # Store previous findings for change detection diff
    old_findings = []
    inv = db.get_investigation(investigation_id)
    if inv:
        old_findings = inv.get("findings", [])

    if watch_id:
        db.update_watchlist_status(watch_id, "SCANNING", last_scan_at=db.now())

    job_id = db.create_job(
        investigation_id=investigation_id,
        job_type="scheduled_crawl",
        payload={"watch_id": watch_id, "target": target, "investigation_id": investigation_id},
    )

    def _worker():
        try:
            # 1. REUSE EXISTING CRAWLER!
            run_crawler(
                db=db,
                job_id=job_id,
                investigation_id=investigation_id,
                actor_id=actor_id,
                urls=[target] if target.startswith("http") else [f"http://{target}"],
                target=target,
                workers=3,
            )

            # 2. Fetch new findings after crawl
            new_inv = db.get_investigation(investigation_id)
            new_findings = new_inv.get("findings", []) if new_inv else []

            # 3. Change Detection using tracking.diff
            from .tracking import diff
            diff_res = diff(old_findings, new_findings)
            counts = diff_res.get("counts", {})
            added_cnt = counts.get("added", 0)
            changed_cnt = counts.get("changed", 0)
            removed_cnt = counts.get("removed", 0)

            now_str = db.now()
            interval_min = watch.get("interval_minutes", 60)
            next_scan_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=int(interval_min))
            next_scan_at = next_scan_dt.isoformat()

            if added_cnt > 0 or changed_cnt > 0 or removed_cnt > 0:
                final_status = "CHANGES_DETECTED"
                msg = f"Monitoring scan detected changes for {target}: +{added_cnt} new, ~{changed_cnt} changed, -{removed_cnt} removed"

                db.add_timeline_event(
                    investigation_id=investigation_id,
                    event_type="change_detected",
                    message=msg,
                    payload=diff_res,
                )

                db.add_alert(
                    investigation_id=investigation_id,
                    actor_id=actor_id,
                    source="monitoring_scheduler",
                    alert_type="change_detected",
                    severity="high" if added_cnt > 3 else "medium",
                    message=msg,
                    confidence=0.95,
                )

                if watch_id:
                    db.update_watchlist_status(
                        watch_id,
                        status="CHANGES_DETECTED",
                        last_scan_at=now_str,
                        next_scan_at=next_scan_at,
                        last_change_at=now_str,
                    )
            else:
                msg = f"Monitoring scan completed for {target}: No change detected."
                db.add_timeline_event(
                    investigation_id=investigation_id,
                    event_type="no_change_detected",
                    message=msg,
                )

                if watch_id:
                    db.update_watchlist_status(
                        watch_id,
                        status="NO_CHANGE",
                        last_scan_at=now_str,
                        next_scan_at=next_scan_at,
                    )
        except Exception as exc:
            now_str = db.now()
            err_msg = f"Monitoring scan failed for {target}: {exc}"
            db.add_alert(
                investigation_id=investigation_id,
                actor_id=actor_id,
                source="monitoring_scheduler",
                alert_type="scan_failed",
                severity="high",
                message=err_msg,
            )
            if watch_id:
                db.update_watchlist_status(watch_id, status="SCAN_FAILED", last_scan_at=now_str)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    return {
        "status": "RUNNING",
        "job_id": job_id,
        "investigation_id": investigation_id,
        "watch_id": watch_id,
    }


def _scheduled_scan(
    watch: dict[str, Any],
):
    return run_monitoring_scan(db, watch)


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


@app.get(
    "/{page}.html",
    response_class=HTMLResponse,
)
def serve_html_page(page: str):
    if page == "graph":
        page = "correlation"
    html_path = Path(WEB_PATH) / f"{page}.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail=f"Page {page}.html not found")



# ============================================================
# HEALTH
# ============================================================

# ============================================================
# HEALTH & DASHBOARD & MONITORING
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


@app.get("/api/dashboard")
def get_dashboard_data():
    summary = db.get_monitoring_summary()
    watchlist_items = db.list_watchlist()
    investigations_list = _investigations()[:10]
    alerts_list = db.list_alerts(limit=10)
    
    with db.connect() as conn:
        recent_activity = db._rows(
            conn.execute(
                """
                SELECT * FROM sih_investigation_timeline
                ORDER BY created_at DESC LIMIT 15
                """
            ).fetchall()
        )

    return {
        "summary": summary,
        "monitored_sources": watchlist_items,
        "recent_activity": recent_activity,
        "recent_investigations": investigations_list,
        "alerts": alerts_list,
    }


@app.get("/api/monitoring")
def get_monitoring_page_data():
    summary = db.get_monitoring_summary()
    watchlist_items = db.list_watchlist()
    alerts_list = db.list_alerts(limit=50)
    with db.connect() as conn:
        recent_activity = db._rows(
            conn.execute(
                """
                SELECT * FROM sih_investigation_timeline
                WHERE event_type IN ('change_detected', 'no_change_detected', 'crawl_completed', 'crawl_started', 'crawl_failed', 'ALERT_GENERATED')
                ORDER BY created_at DESC LIMIT 20
                """
            ).fetchall()
        )

    return {
        "summary": summary,
        "watchlist": watchlist_items,
        "alerts": alerts_list,
        "recent_activity": recent_activity,
    }


class WatchAddRequest(BaseModel):
    target: str
    investigation_id: Optional[str] = None
    actor_id: Optional[str] = None
    interval_minutes: int = 60


@app.post("/api/watchlist")
def add_watchlist_item(req: WatchAddRequest):
    watch_id = db.add_watchlist(
        target=req.target,
        investigation_id=req.investigation_id,
        actor_id=req.actor_id,
        interval_minutes=req.interval_minutes,
    )
    return {"status": "ok", "watch_id": watch_id, "message": f"Added {req.target} to watchlist."}


@app.get("/api/watchlist")
def list_watchlist_endpoint():
    return db.list_watchlist()


@app.post("/api/watchlist/{watch_id}/scan-now")
def scan_watchlist_item_now(watch_id: str):
    if VERCEL_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "HOSTED_DEMO_MODE",
                "message": (
                    "Live monitoring scans are disabled in this "
                    "hosted demonstration. The displayed watchlist "
                    "and alerts are controlled demonstration data. "
                    "Run PRALAYX locally for authorized live monitoring."
                ),
            },
        )

    items = db.list_watchlist()

    item = next(
        (
            x
            for x in items
            if x.get("watch_id") == watch_id
        ),
        None,
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Watchlist item not found",
        )

    return run_monitoring_scan(
        db,
        item,
    )
    

@app.post("/api/watchlist/{watch_id}/pause")
def pause_watchlist_item(watch_id: str):
    db.set_watchlist_enabled(watch_id, False)
    db.update_watchlist_status(watch_id, "PAUSED")
    return {"status": "ok", "message": "Watchlist item paused."}


@app.post("/api/watchlist/{watch_id}/resume")
def resume_watchlist_item(watch_id: str):
    db.set_watchlist_enabled(watch_id, True)
    db.update_watchlist_status(watch_id, "IDLE")
    return {"status": "ok", "message": "Watchlist item resumed."}


@app.delete("/api/watchlist/{watch_id}")
def remove_watchlist_item(watch_id: str):
    db.remove_watchlist(watch_id)
    return {"status": "ok", "message": "Watchlist item removed."}


@app.get("/api/alerts")
def get_alerts_endpoint(status: Optional[str] = None, investigation_id: Optional[str] = None):
    return {"alerts": db.list_alerts(status=status, investigation_id=investigation_id)}


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert_endpoint(alert_id: str):
    db.update_alert_status(alert_id, "ACKNOWLEDGED")
    return {"status": "ok", "message": "Alert acknowledged."}


@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert_endpoint(alert_id: str):
    db.update_alert_status(alert_id, "RESOLVED")
    return {"status": "ok", "message": "Alert resolved."}


@app.get("/api/search")
def global_search_endpoint(q: str = Query(min_length=1)):
    term = f"%{q.strip()}%"
    with db.connect() as conn:
        invs = db._rows(conn.execute("SELECT * FROM sih_investigations WHERE investigation_id LIKE ? OR target LIKE ? OR notes LIKE ?", (term, term, term)).fetchall())
        findings = db._rows(conn.execute("SELECT * FROM sih_findings WHERE value LIKE ? OR finding_type LIKE ? OR source LIKE ? LIMIT 50", (term, term, term)).fetchall())
        actors = db._rows(conn.execute("SELECT * FROM sih_actors WHERE actor_id LIKE ? OR display_name LIKE ? LIMIT 20", (term, term)).fetchall())
    return {
        "query": q,
        "investigations": invs,
        "findings": findings,
        "actors": actors,
    }


# ============================================================
# CRAWLER
# ============================================================

@app.post("/api/crawl")
def crawl(
    request: Crawl,
):
    if VERCEL_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "HOSTED_DEMO_MODE",
                "message": (
                    "Live crawler execution is disabled in this "
                    "hosted demonstration. Live collection requires "
                    "authorized Tor/network access and runtime "
                    "infrastructure that is not enabled here."
                ),
            },
        )

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
@app.post("/api/investigations")
def investigate(
    request: Investigate,
):
    if VERCEL_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "HOSTED_DEMO_MODE",
                "message": (
                    "Live OSINT execution is disabled in this "
                    "hosted demonstration. External OSINT providers "
                    "require authorized credentials and runtime "
                    "access that are not enabled here."
                ),
            },
        )

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
    if VERCEL_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "HOSTED_DEMO_MODE",
                "message": (
                    "Live OSINT execution is disabled in this "
                    "hosted demonstration. External OSINT providers "
                    "require authorized credentials and runtime "
                    "access that are not enabled here."
                ),
            },
        )

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

    if str(j.get("status") or "").upper() in ("FAILED", "ERROR") and not j.get("error"):
        for evt in reversed(evts):
            if (evt.get("event_type") or "").lower() in ("error", "failed", "warning") and evt.get("message"):
                j["error"] = evt.get("message")
                break
        if not j.get("error"):
            j["error"] = "Process terminated unexpectedly. Check system logs."

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
    inv = _investigation(
        investigation_id,
    )
    if not inv:
        raise HTTPException(
            status_code=404,
            detail="investigation not found",
        )

    # 1. Check if explicit timeline events exist in DB
    events = inv.get("timeline") or []
    if not events:
        events = _db_call("timeline", investigation_id) or _db_call("get_timeline", investigation_id) or []

    # 2. If no timeline events exist, synthesize forensic chronological milestones
    if not events:
        events = []
        created_at = inv.get("created_at") or "2026-09-30T10:00:00"
        target = inv.get("target") or "Dark Web Target"
        
        events.append({
            "event_type": "CASE_INITIALIZED",
            "message": f"Target registered: {target}. Threat actor de-anonymization workspace initialized.",
            "created_at": created_at,
            "timestamp": created_at,
        })

        actor_id = inv.get("actor_id")
        if actor_id:
            events.append({
                "event_type": "ACTOR_ATTRIBUTED",
                "message": f"Attributed initial threat actor profile: {actor_id}",
                "created_at": created_at,
                "timestamp": created_at,
            })

        findings = inv.get("findings") or []
        for f in findings:
            ftype = str(f.get("finding_type") or f.get("type") or "indicator").upper()
            val = f.get("value") or f.get("finding_value") or "Observable"
            src = f.get("source_url") or f.get("source") or "Dark Web"
            f_time = f.get("first_seen") or f.get("created_at") or created_at
            events.append({
                "event_type": f"EXTRACTED_{ftype}",
                "message": f"Extracted {ftype}: '{val}' from {src}",
                "created_at": f_time,
                "timestamp": f_time,
            })

        runs = inv.get("runs") or []
        for r in runs:
            r_type = str(r.get("run_type") or "analysis").upper()
            r_status = str(r.get("status") or "completed").upper()
            r_time = r.get("created_at") or created_at
            events.append({
                "event_type": f"{r_type}_ENGINE",
                "message": f"{r_type} engine executed with final status: {r_status}",
                "created_at": r_time,
                "timestamp": r_time,
            })

        # Sort chronologically by timestamp
        events.sort(key=lambda x: str(x.get("created_at") or ""))

    return events


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
@app.post(
    "/api/investigations/{investigation_id}/reports",
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


@app.get("/api/actors")
def list_actors_endpoint():
    with db.connect() as conn:
        actor_rows = conn.execute("SELECT * FROM sih_actors ORDER BY confidence DESC, created_at DESC").fetchall()
        actors = [dict(r) for r in actor_rows]
        
        for actor in actors:
            aid = actor.get("actor_id")
            inv_row = conn.execute("SELECT investigation_id, target FROM sih_investigations WHERE actor_id = ? LIMIT 1", (aid,)).fetchone()
            if inv_row:
                actor["investigation_id"] = inv_row["investigation_id"]
                actor["target"] = inv_row["target"]
            else:
                actor["investigation_id"] = None
                actor["target"] = None
            
            f_rows = conn.execute("SELECT finding_type, value FROM sih_findings WHERE actor_id = ? OR investigation_id = ?", (aid, actor.get("investigation_id"))).fetchall()
            handles = []
            wallets = []
            pgp_keys = []
            for f in f_rows:
                ft = (f["finding_type"] or "").lower()
                v = f["value"]
                if (ft in ["handle", "username", "alias"] or "handle" in ft) and v not in handles:
                    handles.append(v)
                elif ("crypto" in ft or "btc" in ft or "wallet" in ft) and v not in wallets:
                    wallets.append(v)
                elif ("pgp" in ft) and v not in pgp_keys:
                    pgp_keys.append(v)
            actor["handles"] = handles
            actor["wallets"] = wallets
            actor["pgp_keys"] = pgp_keys

        return {"actors": actors, "total": len(actors)}


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

@app.get("/api/findings/search")
def findings_global_search(
    q: str | None = None,
    finding_type: str | None = None,
    limit: int = 200,
):
    """
    Master Entity Search & Findings Explorer.
    Searches across all investigations, returning matched findings with evidence,
    connected graph relationships, and chronological timeline events.
    """
    if hasattr(db, "search_global_entities"):
        return db.search_global_entities(query=q, finding_type=finding_type, limit=limit)
    return {"query": q, "findings": [], "relationships": [], "timeline": []}


@app.get("/api/findings")
def findings(
    actor: str | None = None,
    finding_type: str | None = None,
    investigation_id: str | None = None,
    confidence: float | None = Query(
        default=None,
        ge=0,
        le=1,
    ),
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    # If scoped to a specific investigation, pull directly from it
    if investigation_id:
        inv = _investigation(investigation_id)
        if not inv:
            raise HTTPException(status_code=404, detail="Investigation not found")
        raw = inv.get("findings", [])
        # Apply optional filters
        if finding_type:
            raw = [f for f in raw if (f.get("finding_type") or "").lower() == finding_type.lower()]
        if q:
            ql = q.lower()
            raw = [f for f in raw if ql in (f.get("value") or "").lower() or ql in (f.get("source") or "").lower()]
        if confidence is not None:
            raw = [f for f in raw if float(f.get("confidence") or 0) >= confidence]
        return raw[:limit]

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


class PersonaComparePayload(BaseModel):
    reference_id: Optional[str] = "Reference"
    reference_posts: Optional[List[Dict[str, Any]]] = None
    reference_text: Optional[str] = None
    candidate_id: Optional[str] = "Candidate"
    candidate_posts: Optional[List[Dict[str, Any]]] = None
    candidate_text: Optional[str] = None
    investigation_id: Optional[str] = None
    persona_a: Optional[Dict[str, Any]] = None
    persona_b: Optional[Dict[str, Any]] = None

PersonaComparePayload.model_rebuild()


@app.post("/api/persona/compare")
def persona_compare(
    request: PersonaComparePayload,
):
    from .persona_adapter import compare_personas_direct, persist_persona_analysis

    if request.persona_a and request.persona_b:
        posts_a = request.persona_a.get("posts", [])
        posts_b = request.persona_b.get("posts", [])
        ref_id = request.persona_a.get("persona_id") or request.reference_id or "Reference"
        cand_id = request.persona_b.get("persona_id") or request.candidate_id or "Candidate"
        return compare_personas_direct(ref_id, posts_a, cand_id, posts_b, request.investigation_id)

    ref_posts = request.reference_posts or []
    if not ref_posts and request.reference_text:
        ref_posts = [{"post_id": "ref-1", "text": request.reference_text}]

    cand_posts = request.candidate_posts or []
    if not cand_posts and request.candidate_text:
        cand_posts = [{"post_id": "cand-1", "text": request.candidate_text}]

    res = compare_personas_direct(
        request.reference_id or "Reference",
        ref_posts,
        request.candidate_id or "Candidate",
        cand_posts,
        request.investigation_id,
    )

    if request.investigation_id and res.get("status") != "error":
        try:
            persist_persona_analysis(db, request.investigation_id, res)
        except Exception:
            pass

    return res


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
def persona_synthetic_demo(
    investigation_id: str | None = Query(default=None),
):
    from .persona_adapter import get_synthetic_rebrand_demo, persist_persona_analysis
    target_inv = investigation_id or "INV-DEMO-2026"
    res = get_synthetic_rebrand_demo(target_inv)
    if investigation_id:
        try:
            persist_persona_analysis(db, investigation_id, res)
        except Exception:
            pass
    return res


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

    all_misc = []
    for k, v in categories.items():
        all_misc.extend(v)

    return {
        "investigation_id": investigation_id,
        "categories": categories,
        "misconfigurations": all_misc,
        "total_misconfigurations": len(all_misc),
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


@app.get("/api/reports/download-package/{investigation_id}")
async def download_evidence_package(investigation_id: str):
    """Generates and downloads a complete Law Enforcement Evidence Package (.zip)."""
    import zipfile
    import hashlib

    inv = db.get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    pkg_dir = os.path.join(REPORTS_PATH, "packages")
    os.makedirs(pkg_dir, exist_ok=True)
    zip_path = os.path.join(pkg_dir, f"{investigation_id}_forensic_package.zip")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 1. Case Summary JSON
        json_bytes = json.dumps(inv, indent=2, default=str).encode('utf-8')
        zipf.writestr("forensic_data.json", json_bytes)

        # 2. Evidence Manifest CSV
        findings = inv.get("findings", [])
        csv_lines = ["finding_id,finding_type,finding_value,evidence_source_url,confidence,collected_at\n"]
        for f in findings:
            csv_lines.append(f'{f.get("finding_id")},{f.get("finding_type")},"{f.get("finding_value")}","{f.get("evidence_source_url")}",{f.get("confidence")},{f.get("evidence_collected_at")}\n')
        zipf.writestr("evidence_manifest.csv", "".join(csv_lines).encode('utf-8'))

        # 3. SHA256 Checksums
        h1 = hashlib.sha256(json_bytes).hexdigest()
        h2 = hashlib.sha256("".join(csv_lines).encode('utf-8')).hexdigest()
        checksum_content = f"SHA256 (forensic_data.json) = {h1}\nSHA256 (evidence_manifest.csv) = {h2}\nGenerated By: PRALAYX Law Enforcement Evidence Engine (SIH26151)\n"
        zipf.writestr("SHA256_CHECKSUMS.txt", checksum_content.encode('utf-8'))

        # 4. Summary Text File
        summary_txt = f"PRALAYX FORENSIC EVIDENCE PACKAGE\nCase ID: {investigation_id}\nTarget: {inv.get('target')}\nTotal Findings: {len(findings)}\nStatus: {inv.get('status')}\n"
        zipf.writestr("README_CASE_SUMMARY.txt", summary_txt.encode('utf-8'))

    return FileResponse(zip_path, filename=f"{investigation_id}_forensic_package.zip", media_type="application/zip")


# ============================================================
# INVESTIGATION SPECIFIC FINDINGS & GRAPH & OSINT & PERSONA
# ============================================================

@app.get("/api/investigations/{investigation_id}/findings")
def investigation_findings(investigation_id: str):
    inv = _investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    findings = inv.get("findings", [])
    return {
        "investigation_id": investigation_id,
        "findings": findings,
        "total_findings": len(findings)
    }

@app.get("/api/investigations/{investigation_id}/graph")
def investigation_graph(investigation_id: str):
    inv = _investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    target = inv.get("target") or investigation_id
    findings = inv.get("findings", [])
    relationships = inv.get("relationships", [])

    nodes = [
        {"id": f"INV-{investigation_id}", "label": target, "type": "target", "category": "target"}
    ]
    edges = []

    actor_id = inv.get("actor_id")
    if actor_id:
        nodes.append({"id": actor_id, "label": f"Actor: {actor_id}", "type": "actor", "category": "actor"})
        edges.append({"source": f"INV-{investigation_id}", "target": actor_id, "type": "attributed_to", "label": "Attributed To"})

    seen_nodes = {f"INV-{investigation_id}", actor_id} if actor_id else {f"INV-{investigation_id}"}

    for f in findings:
        f_id = f.get("finding_id") or f"FIND-{id(f)}"
        val = f.get("value") or f.get("finding_value") or "Indicator"
        ftype = f.get("finding_type") or f.get("type") or "finding"
        
        if f_id not in seen_nodes:
            nodes.append({
                "id": f_id,
                "label": str(val)[:30],
                "type": ftype,
                "category": ftype,
                "confidence": f.get("confidence", 0.5),
                "source": f.get("source", "Dark Web")
            })
            seen_nodes.add(f_id)
            edges.append({
                "source": f"INV-{investigation_id}",
                "target": f_id,
                "type": "extracted_finding",
                "label": ftype.upper()
            })

    for r in relationships:
        r_id = r.get("relationship_id") or f"REL-{id(r)}"
        src = r.get("from_value") or r.get("source") or f"INV-{investigation_id}"
        tgt = r.get("to_value") or r.get("target") or "Unknown"
        rel_type = r.get("relationship_type") or "connected_to"
        
        if src not in seen_nodes:
            src_type = r.get("from_type") or "entity"
            nodes.append({"id": src, "label": str(src)[:30], "type": src_type, "category": src_type})
            seen_nodes.add(src)
        if tgt not in seen_nodes:
            tgt_type = r.get("to_type") or "entity"
            nodes.append({"id": tgt, "label": str(tgt)[:30], "type": tgt_type, "category": tgt_type})
            seen_nodes.add(tgt)

        edges.append({
            "source": src,
            "target": tgt,
            "type": rel_type,
            "label": rel_type.replace("_", " ").upper(),
            "confidence": r.get("confidence", 0.8)
        })

    return {
        "investigation_id": investigation_id,
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }

@app.get("/api/investigations/{investigation_id}/persona")
def investigation_persona(investigation_id: str):
    inv = _investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    findings = inv.get("findings", [])
    persona_findings = [f for f in findings if "stylometry" in str(f.get("finding_type","")).lower() or "persona" in str(f.get("source","")).lower()]
    
    return {
        "investigation_id": investigation_id,
        "target": inv.get("target"),
        "actor_id": inv.get("actor_id"),
        "persona_findings": persona_findings,
        "has_profile": len(persona_findings) > 0
    }

@app.post("/api/investigations/{investigation_id}/osint")
def run_investigation_osint(investigation_id: str, request: Investigate):
    if VERCEL_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "HOSTED_DEMO_MODE",
                "message": (
                    "Live OSINT execution is disabled in this "
                    "hosted demonstration. External OSINT providers "
                    "require authorized credentials and runtime "
                    "access that are not enabled here."
                ),
            },
        )

    inv = _investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

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
            "actor_id": inv.get("actor_id") or "ACT-OSINT",
            "target": request.target,
            "target_type": request.target_type,
        },
        daemon=True,
    )
    thread.start()

    return {
        "job_id": job_id,
        "investigation_id": investigation_id,
        "status": "RUNNING",
        "target": request.target,
        "target_type": request.target_type
    }
