from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import (
    HTMLResponse,
    Response,
)
from pydantic import BaseModel, Field

from .analysis import (
    behavior,
    compare,
    stylometry,
)
from .config import (
    DB_PATH,
    SCHEMA_PATH,
)
from .crawler_runner import (
    run as run_crawler,
)
from .database import DB
from .engine_runner import (
    run_osint,
)
from .reports import (
    actor,
    csv_bytes,
    html_report,
    network,
)
from .tracking import Scheduler


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
# APPLICATION
# ============================================================

app = FastAPI(
    title="SIH26151 Threat Intelligence Platform",
    version="1.0.0",
)


# ============================================================
# REQUEST MODELS
# ============================================================

class Crawl(BaseModel):
    urls: list[str] = Field(
        min_length=1
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
    posts: list[dict]


class ComparePersona(BaseModel):
    persona_a: dict
    persona_b: dict


# ============================================================
# HOME
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def home():
    html_path = (
        Path(__file__)
        .resolve()
        .parent
        .parent
        / "web"
        / "index.html"
    )

    if not html_path.exists():
        raise HTTPException(
            500,
            "web/index.html not found",
        )

    return html_path.read_text(
        encoding="utf-8"
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "database": DB_PATH,
        "schema": SCHEMA_PATH,
    }


# ============================================================
# CRAWLER
# ============================================================

@app.post("/api/crawl")
def crawl(request: Crawl):
    investigation_id, actor_id = (
        db.create_investigation(
            request.target
            or request.urls[0],
            "username"
            if request.target
            else "url",
            "crawler",
        )
    )

    job_id = db.create_job(
        "crawl",
        investigation_id,
        request.model_dump(),
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
    }


# ============================================================
# OSINT
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
        "osint",
        investigation_id,
        request.model_dump(),
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
    }


# ============================================================
# JOB
# ============================================================

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = db.job(job_id)

    if not job:
        raise HTTPException(
            404,
            "job not found",
        )

    return {
        "job": job,
        "events": db.events(job_id),
    }


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket(
    "/ws/jobs/{job_id}"
)
async def websocket_job(
    websocket: WebSocket,
    job_id: str,
):
    await websocket.accept()

    sent = set()

    try:
        while True:
            job = db.job(job_id)

            if not job:
                await websocket.send_json(
                    {
                        "event_type": "error",
                        "message": "job not found",
                    }
                )
                return

            events = db.events(job_id)

            for event in events:
                event_id = event[
                    "event_id"
                ]

                if event_id in sent:
                    continue

                sent.add(event_id)

                try:
                    event["payload"] = json.loads(
                        event["payload"]
                    )
                except Exception:
                    pass

                await websocket.send_json(
                    event
                )

            if job["status"] in (
                "completed",
                "failed",
            ):
                await websocket.send_json(
                    {
                        "event_type": "terminal",
                        "status": job["status"],
                    }
                )

                return

            await asyncio.sleep(0.8)

    except WebSocketDisconnect:
        return


# ============================================================
# INVESTIGATIONS
# ============================================================

@app.get("/api/investigations")
def investigations():
    return db.investigations()


@app.get(
    "/api/investigations/{investigation_id}"
)
def investigation(
    investigation_id: str,
):
    result = db.investigation(
        investigation_id
    )

    if not result:
        raise HTTPException(
            404,
            "investigation not found",
        )

    return result


# ============================================================
# REPORTS
# ============================================================

@app.get(
    "/api/reports/{investigation_id}/network"
)
def network_report(
    investigation_id: str,
):
    result = db.investigation(
        investigation_id
    )

    if not result:
        raise HTTPException(
            404,
            "investigation not found",
        )

    return network(result)


@app.get(
    "/api/reports/{investigation_id}/threat-actor"
)
def actor_report(
    investigation_id: str,
):
    result = db.investigation(
        investigation_id
    )

    if not result:
        raise HTTPException(
            404,
            "investigation not found",
        )

    return actor(result)


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
    return db.filtered_findings(
        actor=actor,
        ftype=finding_type,
        confidence=confidence,
        q=q,
    )


# ============================================================
# EXPORT
# ============================================================

@app.get(
    "/api/export/{investigation_id}/json"
)
def export_json(
    investigation_id: str,
):
    result = db.investigation(
        investigation_id
    )

    if not result:
        raise HTTPException(
            404,
            "investigation not found",
        )

    return Response(
        json.dumps(
            result,
            indent=2,
            default=str,
        ),
        media_type="application/json",
        headers={
            "Content-Disposition":
                f'attachment; filename="{investigation_id}.json"'
        },
    )


@app.get(
    "/api/export/{investigation_id}/csv"
)
def export_csv(
    investigation_id: str,
):
    result = db.investigation(
        investigation_id
    )

    if not result:
        raise HTTPException(
            404,
            "investigation not found",
        )

    return Response(
        csv_bytes(
            result["findings"]
        ),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="{investigation_id}.csv"'
        },
    )


@app.get(
    "/api/export/{investigation_id}/html"
)
def export_html(
    investigation_id: str,
):
    result = db.investigation(
        investigation_id
    )

    if not result:
        raise HTTPException(
            404,
            "investigation not found",
        )

    return Response(
        html_report(
            "SIH26151 Investigation",
            result,
        ),
        media_type="text/html",
        headers={
            "Content-Disposition":
                f'attachment; filename="{investigation_id}.html"'
        },
    )


# ============================================================
# WATCHLIST
# ============================================================

@app.post("/api/watchlist")
def add_watch(request: Watch):
    return {
        "watch_id": db.watch(
            request.actor_id,
            request.interval_minutes,
        )
    }


@app.get("/api/watchlist")
def watchlist():
    return db.watchlist()


# ============================================================
# ALERTS
# ============================================================

@app.get("/api/alerts")
def alerts(
    unread: bool = False,
):
    return db.alerts(unread)


@app.post(
    "/api/alerts/{alert_id}/read"
)
def read_alert(
    alert_id: str,
):
    db.mark_alert(alert_id)

    return {
        "ok": True
    }


# ============================================================
# PERSONA / STYLOMETRY
# ============================================================

@app.post("/api/persona/analyze")
def persona(
    request: Persona,
):
    return {
        "stylometry": stylometry(
            request.posts
        ),
        "behavior": behavior(
            request.posts
        ),
    }


@app.post("/api/persona/compare")
def persona_compare(
    request: ComparePersona,
):
    return {
        "similarity": compare(
            request.persona_a,
            request.persona_b,
        ),
        "interpretation": (
            "Similarity is a ranking signal, "
            "not attribution proof."
        ),
    }


# ============================================================
# STARTUP / SHUTDOWN
# ============================================================

scheduler = None


@app.on_event("startup")
def startup():
    global scheduler

    # Keep scheduler initialization isolated.
    # The current tracking implementation is process-local.
    try:
        scheduler = Scheduler(
            db,
            lambda item: None,
        )
        scheduler.start()
    except Exception:
        scheduler = None


@app.on_event("shutdown")
def shutdown():
    global scheduler

    if scheduler is not None:
        try:
            scheduler.stop_event.set()
        except Exception:
            pass

    db.close()
