from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

load_dotenv()

ENGINE_PATH = os.getenv("OSINT_ENGINE_PATH", "../osint-engine")
ENGINE_PATH = str(Path(ENGINE_PATH).resolve())
if ENGINE_PATH not in sys.path:
    sys.path.insert(0, ENGINE_PATH)

from src.database import OSINTDatabase  # noqa: E402
from src.engine import OSINTEngine  # noqa: E402
from src.models import Identifier, InvestigationInput  # noqa: E402

DB_PATH = os.getenv("OSINT_DB_PATH", "../DarkWeb-Deanonymization/data/crawler.db")
DB_PATH = str(Path(DB_PATH).resolve())
SCHEMA_PATH = str(Path(os.getenv("SHARED_SCHEMA_PATH", str(Path(__file__).resolve().parents[2] / "shared" / "schema_sqlite.sql"))).resolve())

app = FastAPI(title="SIH26151 Investigation Platform API", version="0.1.0")


def db() -> OSINTDatabase:
    database = OSINTDatabase(DB_PATH)
    database.migrate(SCHEMA_PATH)
    return database


class IdentifierRequest(BaseModel):
    type: Literal["username", "email", "url", "domain", "dns", "ip", "pgp", "crypto"]
    value: str = Field(min_length=1)
    source: str = "manual"
    source_url: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class InvestigateRequest(BaseModel):
    target: str | None = None
    target_type: str | None = None
    identifiers: list[IdentifierRequest] = Field(default_factory=list)
    actor_id: str | None = None
    notes: str | None = None


class CrawlRequest(BaseModel):
    target: str = Field(min_length=1)


def run_osint_job(job_id: str, investigation_id: str, actor_id: str | None, identifiers: list[Identifier]):
    database = db()
    try:
        database.update_job(job_id, "running", 0.05)
        database.add_job_event(job_id, investigation_id, "started", "OSINT investigation started")
        engine = OSINTEngine(db=database)
        database.add_job_event(job_id, investigation_id, "engine", f"Loaded {len(engine.scanners)} scanners and {len(engine.providers)} providers")
        investigation = InvestigationInput(
            investigation_id=investigation_id,
            actor_id=actor_id,
            identifiers=identifiers,
        )
        database.update_job(job_id, "running", 0.15)
        result = engine.run(investigation)
        database.update_job(job_id, "completed", 1.0)
        database.add_job_event(job_id, investigation_id, "completed", f"OSINT completed: {len(result.findings)} findings", metadata={"errors": result.errors})
    except Exception as exc:
        database.update_job(job_id, "failed", error=str(exc))
        database.add_job_event(job_id, investigation_id, "failed", str(exc), level="error")
    finally:
        database.close()


def run_crawler_job(job_id: str, investigation_id: str, target: str):
    database = db()
    try:
        command = os.getenv("CRAWLER_COMMAND", "").strip()
        database.add_job_event(job_id, investigation_id, "crawler", "Crawler job queued")
        if not command:
            database.update_job(job_id, "failed", error="CRAWLER_COMMAND is not configured")
            database.add_job_event(job_id, investigation_id, "failed", "Set CRAWLER_COMMAND after confirming the crawler CLI", level="error")
            return
        database.update_job(job_id, "running", 0.05)
        env = os.environ.copy()
        env["TARGET"] = target
        env["JOB_ID"] = job_id
        process = subprocess.Popen(command, shell=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout or []:
            line = line.rstrip()
            if line:
                database.add_job_event(job_id, investigation_id, "crawler_output", line)
        rc = process.wait()
        if rc == 0:
            database.update_job(job_id, "completed", 1.0)
            database.add_job_event(job_id, investigation_id, "completed", "Crawler process completed")
        else:
            database.update_job(job_id, "failed", error=f"Crawler exited with code {rc}")
            database.add_job_event(job_id, investigation_id, "failed", f"Crawler exited with code {rc}", level="error")
    except Exception as exc:
        database.update_job(job_id, "failed", error=str(exc))
        database.add_job_event(job_id, investigation_id, "failed", str(exc), level="error")
    finally:
        database.close()


@app.get("/health")
def health():
    database = db()
    try:
        return {"status": "ok", "database": DB_PATH}
    finally:
        database.close()


@app.post("/investigate", status_code=202)
def investigate(payload: InvestigateRequest, background_tasks: BackgroundTasks):
    database = db()
    try:
        if payload.identifiers:
            target = payload.target or payload.identifiers[0].value
            target_type = payload.target_type or payload.identifiers[0].type
        elif payload.target:
            target = payload.target
            target_type = payload.target_type or "username"
        else:
            raise HTTPException(400, "Provide target or at least one identifier")

        iid, actor_id = database.create_investigation(target, target_type, notes=payload.notes, actor_id=payload.actor_id)
        identifiers = [Identifier(**item.model_dump()) for item in payload.identifiers]
        if not identifiers:
            identifiers = [Identifier(type=target_type, value=target, source="manual")]
        database.register_identifiers(iid, actor_id, identifiers)
        job_id = database.create_job(iid, "osint")
        background_tasks.add_task(run_osint_job, job_id, iid, actor_id, identifiers)
        return {"investigation_id": iid, "actor_id": actor_id, "job_id": job_id, "status": "queued"}
    finally:
        database.close()


@app.post("/investigate/from-crawler/{crawler_investigation_id}", status_code=202)
def investigate_from_crawler(crawler_investigation_id: int, background_tasks: BackgroundTasks):
    database = db()
    try:
        crawler = database.get_crawler_investigation(crawler_investigation_id)
        if not crawler:
            raise HTTPException(404, "Crawler investigation not found")
        iid = crawler["session_id"]
        actor_id = database.ensure_actor_for_investigation(iid, crawler.get("target_username"))
        identifiers = database.get_identifiers_from_crawler(iid)
        if not identifiers:
            raise HTTPException(400, "Crawler investigation contains no supported identifiers")
        database.register_identifiers(iid, actor_id, identifiers)
        job_id = database.create_job(iid, "osint")
        background_tasks.add_task(run_osint_job, job_id, iid, actor_id, identifiers)
        return {"investigation_id": iid, "actor_id": actor_id, "job_id": job_id, "identifier_count": len(identifiers), "status": "queued"}
    finally:
        database.close()


@app.post("/crawl", status_code=202)
def crawl(payload: CrawlRequest, background_tasks: BackgroundTasks):
    database = db()
    try:
        # A crawler investigation root is created first so job events have a stable investigation ID.
        iid, _ = database.create_investigation(payload.target, "url", source="crawler")
        job_id = database.create_job(iid, "crawl")
        background_tasks.add_task(run_crawler_job, job_id, iid, payload.target)
        return {"investigation_id": iid, "job_id": job_id, "status": "queued"}
    finally:
        database.close()


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    database = db()
    try:
        job = database.get_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job
    finally:
        database.close()


@app.get("/investigations")
def list_investigations(limit: int = 50):
    database = db()
    try:
        return database.list_investigations(max(1, min(limit, 200)))
    finally:
        database.close()


@app.get("/investigations/{investigation_id}")
def get_investigation(investigation_id: str):
    database = db()
    try:
        result = database.get_investigation(investigation_id)
        if not result:
            raise HTTPException(404, "Investigation not found")
        return result
    finally:
        database.close()


@app.get("/reports/{investigation_id}/network")
def network_report(investigation_id: str):
    database = db()
    try:
        result = database.get_investigation(investigation_id)
        if not result:
            raise HTTPException(404, "Investigation not found")
        return {"investigation_id": investigation_id, "report_type": "network", "findings": result["findings"]}
    finally:
        database.close()


@app.get("/reports/{investigation_id}/threat-actor")
def threat_actor_report(investigation_id: str):
    database = db()
    try:
        result = database.get_investigation(investigation_id)
        if not result:
            raise HTTPException(404, "Investigation not found")
        return {"investigation_id": investigation_id, "report_type": "threat-actor", "identifiers": result["identifiers"], "findings": result["findings"]}
    finally:
        database.close()


@app.websocket("/ws/investigation/{job_id}")
async def investigation_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    last_id = 0
    try:
        while True:
            database = db()
            try:
                job = database.get_job(job_id)
                if not job:
                    await websocket.send_json({"event_type": "error", "message": "Job not found"})
                    return
                events = database.get_job_events(job_id, last_id)
            finally:
                database.close()
            for event in events:
                last_id = event["id"]
                await websocket.send_json(event)
            if job["status"] in {"completed", "failed"} and not events:
                await websocket.send_json({"event_type": "terminal", "status": job["status"]})
                return
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
