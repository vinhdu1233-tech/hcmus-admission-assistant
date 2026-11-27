"""Dependency-free smoke test for an actual Docker Compose stack."""
import json,re,sys,time,urllib.request,http.cookiejar
BASE="http://127.0.0.1:8080/api/product"
MAIL="http://127.0.0.1:8025/api/v2/messages"
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def request(url,body=None):
    data=None if body is None else json.dumps(body).encode()
    r=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"} if data else {})
    with opener.open(r,timeout=10) as f:return json.load(f)
def ready():
    for _ in range(90):
        try:
            assert request(BASE+"/auth/me")["user"] is None
            return
        except Exception:time.sleep(1)
    raise RuntimeError("Docker services not ready")
def otp(email):
    for _ in range(30):
        for x in request(MAIL)["items"]:
            if email in str(x["Content"]["Headers"].get("To",[])):
                m=re.search(r"(?<!\d)\d{6}(?!\d)",x["Content"]["Body"])
                if m:return m.group()
        time.sleep(1)
    raise RuntimeError("MailHog did not receive code")
def main():
    ready();email="docker-smoke@example.test";pw="DockerTest7!"
    if sys.argv[1]=="register":
        assert request(BASE+"/auth/register/code",{"email":email})["ok"]
        assert request(BASE+"/auth/register",{"email":email,"username":"dockersmoke","password":pw,"code":otp(email)})["ok"]
        key=request(BASE+"/push/config")["public_key"];assert key
        from pathlib import Path
        Path("/tmp/docker-f4-key").write_text(key)
    else:
        from pathlib import Path
        assert request(BASE+"/push/config")["public_key"]==Path("/tmp/docker-f4-key").read_text()
    assert request(BASE+"/auth/login",{"identifier":"dockersmoke","password":pw})["user"]["role"]=="student"
    assert request(BASE+"/auth/me")["user"]["username"]=="dockersmoke"
    assert request(BASE+"/calendar?year=2026")["events"]
    assert request(BASE+"/calendar/proposals")["items"]==[]
    print("DOCKER_SMOKE_PASS",sys.argv[1])
if __name__=="__main__":main()
