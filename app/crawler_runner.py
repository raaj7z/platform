import importlib, os, sys

def load_crawler():
    root=os.getenv("CRAWLER_PATH","../DarkWeb-Deanonymization")
    src=os.path.join(root,"src")
    if src not in sys.path: sys.path.insert(0,src)
    return importlib.import_module("service")

def run(db,job_id,urls,target=None,workers=3):
    db.update_job(job_id,status="running",progress=.03)
    db.event(job_id,"status","Crawler started",.03,{"urls":len(urls)})
    try:
        service=load_crawler()
        db.event(job_id,"status","Crawler service loaded",.06)
        result=service.run_crawl(urls,target_username=target,workers=workers,db=None)
        if result.get("error"): raise RuntimeError(result["error"])
        iid,actor_id=db.create_investigation(target or urls[0],"username" if target else "url","crawler")
        db.event(job_id,"collection","Collection completed",.70,result.get("summary",{}))
        for row in result.get("actor_rows",[]):
            value=row.get("value") or row.get("username") or row.get("email")
            if not value: continue
            fid=db.finding(iid,row.get("finding_type") or row.get("type") or "other",
                           str(value),row.get("source","crawler"),
                           row.get("source_url") or row.get("url"),
                           row.get("confidence",.5),row,actor_id)
            sid=db.source(row.get("source","crawler"),row.get("source_url") or row.get("url"))
            db.evidence(fid,sid,"crawler_extraction",row.get("source_url") or row.get("url"),
                        row.get("context") or row.get("content"),{"raw_row":row})
        for row in result.get("network_rows",[]):
            value=row.get("ip_address") or row.get("domain") or row.get("host") or row.get("source_url")
            if not value: continue
            fid=db.finding(iid,"infrastructure",str(value),row.get("source","crawler"),
                           row.get("source_url"),row.get("confidence",.5),row,actor_id)
            sid=db.source(row.get("source","crawler"),row.get("source_url"))
            db.evidence(fid,sid,"network_artifact",row.get("source_url"),metadata={"raw_row":row})
        db.update_job(job_id,status="completed",progress=1,result_ref=iid)
        db.event(job_id,"completed","Investigation ready",1,{"investigation_id":iid})
        return iid
    except Exception as e:
        db.update_job(job_id,status="failed",progress=1,error=str(e))
        db.event(job_id,"error",str(e),1); raise

