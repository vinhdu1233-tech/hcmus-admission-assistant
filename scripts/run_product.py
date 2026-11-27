"""Single-instance supervisor for Node, private API and persistent reminder worker."""
import os,signal,subprocess,sys,time
from urllib.request import urlopen
def main():
    procs=[]
    def stop(*_):
        for p in procs:p.terminate()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        procs.append(subprocess.Popen([sys.executable,"-m","uvicorn","src.api.main:app","--host","127.0.0.1","--port","8000"]))
        for _ in range(60):
            if procs[0].poll() is not None:raise RuntimeError("API stopped")
            try:
                with urlopen("http://127.0.0.1:8000/health",timeout=1) as r:
                    if r.status==200:break
            except Exception:time.sleep(.5)
        else:raise RuntimeError("API not ready")
        procs.append(subprocess.Popen(["node","ui/server.mjs"]))
        procs.append(subprocess.Popen([sys.executable,"-m","src.product_worker"]))
        while all(p.poll() is None for p in procs):time.sleep(1)
        return 1
    finally:
        stop()
        for p in procs:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill()
if __name__=="__main__":raise SystemExit(main())
