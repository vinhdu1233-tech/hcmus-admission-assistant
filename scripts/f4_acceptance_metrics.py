"""Localhost measurements: real authenticated API requests and controlled scheduler time."""
import concurrent.futures,json,math,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
import httpx
from src.product_db import db
from src.product_auth import password_hash
from src.product_worker import queue_reminders,fetch_source,save_snapshot
from src.product_seed import S1
BASE="http://127.0.0.1:5501/api/product"
OUT=Path("product-browser-evidence");OUT.mkdir(exist_ok=True)
def p95(values):return sorted(values)[math.ceil(.95*len(values))-1]
def main():
    clients=[];ids=[];now=datetime.now(timezone.utc);pw="F4Metrics7!"
    hashed=password_hash(pw)
    for n in range(3):
        name=f"metricsstudent{n}"
        with db(True) as c:c.execute("INSERT INTO users(email,username,password_hash,created_at) VALUES (?,?,?,?)",(name+"@example.test",name,hashed,time.time()))
        cl=httpx.Client(base_url=BASE,timeout=10)
        cl.post("/auth/login",json={"identifier":name,"password":pw}).raise_for_status()
        r=cl.post("/calendar/personal",json={"title":f"Private metrics {n}","start":(now+timedelta(days=8)).isoformat(),"end":(now+timedelta(days=9)).isoformat()})
        r.raise_for_status();i=r.json()["id"]
        cl.post("/calendar/reminders",json={"event_id":i,"before_start":[7]}).raise_for_status()
        clients.append(cl);ids.append(i)
    lat=[]
    for _ in range(50):
        t=time.perf_counter();r=clients[0].get("/calendar");lat.append((time.perf_counter()-t)*1000);r.raise_for_status()
    def simulated(n):
        ok=0;times=[]
        for _ in range(10):
            t=time.perf_counter();r=clients[n].get("/calendar");times.append((time.perf_counter()-t)*1000)
            if r.is_success:
                seen={x["id"] for x in r.json()["events"]}
                if ids[n] in seen and all(i not in seen for j,i in enumerate(ids) if j!=n):ok+=1
        return ok,times
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(simulated,range(3)))
    due=(now+timedelta(days=1,seconds=5)).timestamp()
    cycles=0;errors=[]
    for n in range(100):
        try:queue_reminders(due+n);cycles+=1
        except Exception as e:errors.append(type(e).__name__)
    with db() as c:counts=[c.execute("SELECT COUNT(*) FROM notices WHERE event_id=?",(i,)).fetchone()[0] for i in ids]
    summary={"calendar_requests":50,"calendar_p95_ms":round(p95(lat),3),"scheduler_cycles":100,"cycles_success":cycles,"cycle_errors":errors,"notices_per_event":counts,"ccu":3,"isolated_requests":sum(x[0] for x in results),"ccu_requests":30,"ccu_p95_ms":round(p95([t for _,ts in results for t in ts]),3),"environment":"CI localhost Node + FastAPI + SQLite; controlled clock for scheduler; no live push receipt"}
    try:
        raw=fetch_source(S1);save_snapshot(S1,raw)
        summary["live_source"]={"status":"ok","normalized_chars":len(raw)}
    except Exception as e:summary["live_source"]={"status":"unverified","error":type(e).__name__}
    for cl in clients:cl.close()
    (OUT/"f4_metrics.json").write_text(json.dumps(summary,indent=2))
    print("F4_METRICS",json.dumps(summary))
    assert summary["calendar_p95_ms"]<=500 and cycles>=99 and counts==[1,1,1] and summary["isolated_requests"]==30
if __name__=="__main__":main()
