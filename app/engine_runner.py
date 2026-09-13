import os, sys, importlib

def run_osint(db,job_id,iid,target,target_type="other"):
    db.update_job(job_id,status="running",progress=.05)
    db.event(job_id,"status","OSINT engine started",.05,{"target":target})
    try:
        root=os.getenv("OSINT_ENGINE_PATH","../osint-engine")
        if root not in sys.path: sys.path.insert(0,root)
        engine=importlib.import_module("src.engine")
        models=importlib.import_module("src.models")
        identifier=models.Identifier(type=target_type,value=target,source="manual")
        inp=models.InvestigationInput(investigation_id=iid,identifiers=[identifier])
        result=engine.OSINTEngine().run(inp)
        for f in result.findings:
            fid=db.finding(iid,f.finding_type,f.value,f.source,f.source_url,
                           f.confidence,f.metadata)
            sid=db.source(f.source,f.source_url)
            for e in f.evidence:
                db.evidence(fid,sid,"osint_evidence",e.source_url,e.excerpt,e.metadata)
        db.update_job(job_id,status="completed",progress=1,result_ref=iid)
        db.event(job_id,"completed","OSINT analysis completed",1,{"investigation_id":iid})
        return iid
    except Exception as e:
        db.update_job(job_id,status="failed",progress=1,error=str(e))
        db.event(job_id,"error",str(e),1); raise
      
