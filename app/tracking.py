from datetime import datetime, timezone
import threading

def diff(old,current):
    key=lambda x:(x.get("finding_type"),str(x.get("value","")).lower(),x.get("source"))
    a={key(x):x for x in old}; b={key(x):x for x in current}
    added=[v for k,v in b.items() if k not in a]
    return {"added":added,"removed":[v for k,v in a.items() if k not in b],
            "new_platforms":[x for x in added if x.get("finding_type") in ("username","forum_profile")],
            "new_wallets":[x for x in added if x.get("finding_type")=="crypto"],
            "high_confidence":[x for x in added if float(x.get("confidence",0))>=.8]}

class Scheduler:
    def __init__(self,db,callback):
        self.db=db; self.callback=callback; self.stop_event=threading.Event(); self.thread=None
    def start(self):
        if self.thread and self.thread.is_alive(): return False
        self.stop_event.clear(); self.thread=threading.Thread(target=self.loop,daemon=True); self.thread.start(); return True
    def stop(self): self.stop_event.set()
    def loop(self):
        while not self.stop_event.wait(60):
            for item in self.db.watchlist():
                if item.get("enabled"):
                    try:self.callback(item)
                    except Exception: pass

