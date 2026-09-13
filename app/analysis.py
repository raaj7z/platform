from collections import defaultdict
from datetime import datetime, timezone
import re, math

def tokenize(text):
    return re.findall(r"[A-Za-z']+", text or "")

def stylometry(posts):
    texts=[p.get("content","") for p in posts if p.get("content")]
    if not texts:return {"status":"insufficient_data","posts":0}
    words=[w.lower() for t in texts for w in tokenize(t)]
    sentences=sum(max(1,len(re.split(r"[.!?]+",t))-1) for t in texts)
    avg_word=sum(map(len,words))/max(1,len(words))
    vocab=len(set(words))/max(1,len(words))
    punct=sum(1 for t in texts for c in t if c in "!?;,:-")/max(1,sum(map(len,texts)))
    return {"status":"ok","posts":len(texts),"words":len(words),
            "avg_word_length":round(avg_word,3),"type_token_ratio":round(vocab,4),
            "punctuation_density":round(punct,6),"avg_sentence_length":round(len(words)/max(1,sentences),3)}

def behavior(posts):
    hours=[]; cats=defaultdict(int)
    for p in posts:
        ts=p.get("timestamp_parsed")
        if ts:
            try: hours.append(datetime.fromisoformat(ts.replace("Z","+00:00")).hour)
            except Exception: pass
        if p.get("category"): cats[p["category"]]+=1
    return {"posts":len(posts),"posting_hours":sorted(set(hours)),
            "categories":dict(cats),"activity_concentration":round(max(cats.values())/len(posts),3) if posts and cats else 0}

def compare(a,b):
    keys=["avg_word_length","type_token_ratio","punctuation_density","avg_sentence_length"]
    scores=[]
    for k in keys:
        x,y=a.get(k),b.get(k)
        if isinstance(x,(int,float)) and isinstance(y,(int,float)):
            scores.append(max(0,1-abs(x-y)/(abs(x)+abs(y)+1e-9)))
    return round(sum(scores)/len(scores),4) if scores else 0
  
