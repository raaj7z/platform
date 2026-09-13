import json, os, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

def now():
    return datetime.now(timezone.utc).isoformat()

class DB:
    def __init__(self, path=None):
        self.path = path or os.getenv("OSINT_DB_PATH", "data/sih.db")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=15000")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def migrate(self, schema):
        self.conn.executescript(Path(schema).read_text())
        self.conn.commit()

    def _id(self, p): return f"{p}-{uuid.uuid4().hex[:12]}"

    def create_investigation(self, target, target_type="other", source="manual", notes=None):
        iid = str(uuid.uuid4())
        aid = self._id("ACT")
        self.conn.execute(
            "INSERT INTO actors(actor_id,display_name,category,confidence,created_at,updated_at) VALUES(?,?,?,0,?,?)",
            (aid, target, "unknown", now(), now()))
        self.conn.execute(
            """INSERT INTO investigations
            (investigation_id,target,target_type,status,source,notes,actor_id,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (iid,target,target_type,"running",source,notes,aid,now(),now()))
        self.conn.commit()
        return iid, aid

    def create_job(self, job_type, investigation_id=None, payload=None):
        jid=self._id("JOB")
        self.conn.execute(
            """INSERT INTO jobs(job_id,investigation_id,job_type,status,progress,payload,created_at,updated_at)
            VALUES(?,?,?,'queued',0,?,?,?)""",
            (jid,investigation_id,job_type,json.dumps(payload or {}),now(),now()))
        self.conn.commit()
        return jid

    def update_job(self,jid,**kwargs):
        parts=[]; vals=[]
        for k,v in kwargs.items():
            if v is not None:
                parts.append(k+"=?"); vals.append(v)
        parts.append("updated_at=?"); vals.append(now()); vals.append(jid)
        self.conn.execute("UPDATE jobs SET "+",".join(parts)+" WHERE job_id=?",vals)
        self.conn.commit()

    def event(self,jid,etype,message,progress=None,payload=None):
        eid=self._id("EVT")
        self.conn.execute(
            """INSERT INTO job_events(event_id,job_id,event_type,message,progress,payload,created_at)
            VALUES(?,?,?,?,?,?,?)""",
            (eid,jid,etype,message,progress,json.dumps(payload or {}),now()))
        self.conn.commit()

    def job(self,jid):
        r=self.conn.execute("SELECT * FROM jobs WHERE job_id=?",(jid,)).fetchone()
        return dict(r) if r else None

    def events(self,jid):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM job_events WHERE job_id=? ORDER BY rowid",(jid,)).fetchall()]

    def finding(self, iid, ftype, value, source, source_url=None, confidence=.5, metadata=None, actor_id=None):
        fid=self._id("FND")
        self.conn.execute(
            """INSERT INTO findings
            (finding_id,investigation_id,actor_id,finding_type,value,source,source_url,confidence,metadata,first_seen,last_seen)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (fid,iid,actor_id,ftype,value,source,source_url,max(0,min(1,float(confidence))),
             json.dumps(metadata or {}),now(),now()))
        self.conn.commit()
        return fid

    def source(self,name,url=None):
        r=self.conn.execute(
            "SELECT source_id FROM sources WHERE name=? AND COALESCE(url,'')=COALESCE(?, '')",(name,url)).fetchone()
        if r:return r["source_id"]
        sid=self._id("SRC")
        self.conn.execute(
            "INSERT INTO sources(source_id,name,url,source_type,created_at) VALUES(?,?,?,?,?)",
            (sid,name or "unknown",url,"external",now()))
        self.conn.commit(); return sid

    def evidence(self,fid,sid,etype,url=None,excerpt=None,metadata=None):
        eid=self._id("EVD")
        self.conn.execute(
            """INSERT INTO evidence(evidence_id,finding_id,source_id,evidence_type,source_url,excerpt,metadata,collected_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (eid,fid,sid,etype,url,excerpt,json.dumps(metadata or {}),now()))
        self.conn.commit(); return eid

    def investigation(self,iid):
        r=self.conn.execute("SELECT * FROM investigations WHERE investigation_id=?",(iid,)).fetchone()
        if not r:return None
        out=dict(r)
        out["findings"]=[dict(x) for x in self.conn.execute(
            "SELECT * FROM findings WHERE investigation_id=? ORDER BY first_seen DESC",(iid,)).fetchall()]
        out["observations"]=[dict(x) for x in self.conn.execute(
            "SELECT * FROM observations WHERE investigation_id=? ORDER BY observed_at DESC",(iid,)).fetchall()]
        return out

    def investigations(self,limit=100):
        return [dict(x) for x in self.conn.execute(
            "SELECT * FROM investigations ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()]

    def actors(self):
        return [dict(x) for x in self.conn.execute(
            "SELECT * FROM actors ORDER BY updated_at DESC").fetchall()]

    def watch(self,actor_id,interval_minutes=60):
        wid=self._id("WCH")
        self.conn.execute(
            """INSERT INTO watchlist(watch_id,actor_id,interval_minutes,enabled,last_scan_at,created_at,updated_at)
            VALUES(?,?,?,1,NULL,?,?)""",(wid,actor_id,interval_minutes,now(),now()))
        self.conn.commit(); return wid

    def watchlist(self):
        return [dict(x) for x in self.conn.execute("SELECT * FROM watchlist ORDER BY created_at DESC").fetchall()]

    def alert(self,actor_id,fid,atype,message,confidence=.5):
        aid=self._id("ALT")
        self.conn.execute(
            """INSERT INTO alerts(alert_id,actor_id,finding_id,alert_type,message,confidence,is_read,created_at)
            VALUES(?,?,?,?,?,?,0,?)""",(aid,actor_id,fid,atype,message,confidence,now()))
        self.conn.commit(); return aid

    def alerts(self,unread=False):
        q="SELECT * FROM alerts"
        if unread:q+=" WHERE is_read=0"
        q+=" ORDER BY created_at DESC LIMIT 200"
        return [dict(x) for x in self.conn.execute(q).fetchall()]

    def mark_alert(self,aid):
        self.conn.execute("UPDATE alerts SET is_read=1 WHERE alert_id=?",(aid,)); self.conn.commit()

    def filtered_findings(self, actor=None, ftype=None, confidence=None, q=None):
        sql="SELECT * FROM findings WHERE 1=1"; p=[]
        if actor: sql+=" AND actor_id=?"; p.append(actor)
        if ftype: sql+=" AND finding_type=?"; p.append(ftype)
        if confidence is not None: sql+=" AND confidence>=?"; p.append(confidence)
        if q: sql+=" AND lower(value) LIKE ?"; p.append("%"+q.lower()+"%")
        sql+=" ORDER BY last_seen DESC"
        return [dict(x) for x in self.conn.execute(sql,p).fetchall()]
      
