from __future__ import annotations
import asyncio, json, threading
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from database import DB
from crawler_runner import run as run_crawler
from engine_runner import run_osint
from reports import network, actor, csv_bytes, html_report
from analysis import stylometry, behavior, compare
from tracking import Scheduler

db=DB()
from config import SCHEMA_PATH
if __import__("pathlib").Path(SCHEMA_PATH).exists(): db.migrate(SCHEMA_PATH)

app=FastAPI(title="SIH26151 Threat Intelligence Platform",version="1.0.0")

class Crawl(BaseModel):
    urls:list[str]=Field(min_length=1); target:str|None=None; workers:int=Field(3,ge=1,le=10)
class Investigate(BaseModel):
    target:str; target_type:str="other"; notes:str|None=None
class Watch(BaseModel):
    actor_id:str; interval_minutes:int=Field(60,ge=5)
class Persona(BaseModel):
    posts:list[dict]
class ComparePersona(BaseModel):
    persona_a:dict; persona_b:dict

@app.get("/",response_class=HTMLResponse)
def home():
    return __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("web/index.html").read_text()

@app.post("/api/crawl")
def crawl(r:Crawl):
    iid,actor_id=db.create_investigation(r.target or r.urls[0],"username" if r.target else "url","crawler")
    jid=db.create_job("crawl",iid,r.model_dump())
    threading.Thread(target=run_crawler,args=(db,jid,r.urls,r.target,r.workers),daemon=True).start()
    return {"job_id":jid,"investigation_id":iid,"actor_id":actor_id}

@app.post("/api/investigate")
def investigate(r:Investigate):
    iid,actor_id=db.create_investigation(r.target,r.target_type,"manual",r.notes)
    jid=db.create_job("osint",iid,r.model_dump())
    threading.Thread(target=run_osint,args=(db,jid,iid,r.target,r.target_type),daemon=True).start()
    return {"job_id":jid,"investigation_id":iid,"actor_id":actor_id}

@app.get("/api/jobs/{jid}")
def job(jid):
    x=db.job(jid)
    if not x:raise HTTPException(404,"job not found")
    return {"job":x,"events":db.events(jid)}

@app.websocket("/ws/jobs/{jid}")
async def ws(ws:WebSocket,jid:str):
    await ws.accept(); sent=set()
    try:
        while True:
            x=db.job(jid)
            if not x:return
            for e in db.events(jid):
                if e["event_id"] in sent:continue
                sent.add(e["event_id"])
                try:e["payload"]=json.loads(e["payload"])
                except:pass
                await ws.send_json(e)
            if x["status"] in ("completed","failed"):
                await ws.send_json({"event_type":"terminal","status":x["status"]});return
            await asyncio.sleep(.8)
    except WebSocketDisconnect:pass

@app.get("/api/investigations")
def investigations():return db.investigations()
@app.get("/api/investigations/{iid}")
def investigation(iid):
    x=db.investigation(iid)
    if not x:raise HTTPException(404,"investigation not found")
    return x

@app.get("/api/reports/{iid}/network")
def network_report(iid):
    x=db.investigation(iid)
    if not x:raise HTTPException(404,"not found")
    return network(x)
@app.get("/api/reports/{iid}/threat-actor")
def actor_report(iid):
    x=db.investigation(iid)
    if not x:raise HTTPException(404,"not found")
    return actor(x)

@app.get("/api/findings")
def findings(actor:str|None=None,finding_type:str|None=None,confidence:float|None=Query(None,ge=0,le=1),q:str|None=None):
    return db.filtered_findings(actor,finding_type,confidence,q)

@app.get("/api/export/{iid}/json")
def export_json(iid):
    x=db.investigation(iid)
    if not x:raise HTTPException(404,"not found")
    return Response(json.dumps(x,indent=2,default=str),media_type="application/json",
                    headers={"Content-Disposition":f'attachment; filename="{iid}.json"'})
@app.get("/api/export/{iid}/csv")
def export_csv(iid):
    x=db.investigation(iid)
    if not x:raise HTTPException(404,"not found")
    return Response(csv_bytes(x["findings"]),media_type="text/csv",
                    headers={"Content-Disposition":f'attachment; filename="{iid}.csv"'})
@app.get("/api/export/{iid}/html")
def export_html(iid):
    x=db.investigation(iid)
    if not x:raise HTTPException(404,"not found")
    return Response(html_report("SIH26151 Investigation",x),media_type="text/html",
                    headers={"Content-Disposition":f'attachment; filename="{iid}.html"'})

@app.post("/api/watchlist")
def add_watch(r:Watch):return {"watch_id":db.watch(r.actor_id,r.interval_minutes)}
@app.get("/api/watchlist")
def watchlist():return db.watchlist()
@app.get("/api/alerts")
def alerts(unread:bool=False):return db.alerts(unread)
@app.post("/api/alerts/{aid}/read")
def read_alert(aid):db.mark_alert(aid);return {"ok":True}

@app.post("/api/persona/analyze")
def persona(r:Persona):
    return {"stylometry":stylometry(r.posts),"behavior":behavior(r.posts)}
@app.post("/api/persona/compare")
def persona_compare(r:ComparePersona):
    return {"similarity":compare(r.persona_a,r.persona_b),
            "interpretation":"Similarity is a ranking signal, not attribution proof."}
