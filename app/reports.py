import csv, io, json, html

def network(report):
    return {"investigation_id":report["investigation_id"],
            "items":[f for f in report["findings"] if f["finding_type"]=="infrastructure"]}

def actor(report):
    return {"investigation_id":report["investigation_id"],
            "items":[f for f in report["findings"] if f["finding_type"]!="infrastructure"]}

def csv_bytes(rows):
    out=io.StringIO(); fields=sorted({k for r in rows for k in r.keys()})
    w=csv.DictWriter(out,fieldnames=fields); w.writeheader()
    for r in rows:w.writerow({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()})
    return out.getvalue().encode()

def html_report(title, data):
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{html.escape(title)}</title>
    <style>body{{font-family:system-ui;max-width:1100px;margin:30px auto}}pre{{white-space:pre-wrap;background:#f4f4f5;padding:18px;border-radius:12px}}</style>
    </head><body><h1>{html.escape(title)}</h1><pre>{html.escape(json.dumps(data,indent=2,default=str))}</pre></body></html>""".encode()
  
