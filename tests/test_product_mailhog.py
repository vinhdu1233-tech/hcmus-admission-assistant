"""SMTP integration: run with MailHog service. No real emails leave the CI runner."""
import os,re,time
import pytest,httpx
from fastapi.testclient import TestClient
from src.api.main import app
@pytest.mark.skipif(os.getenv("RUN_MAILHOG_TEST")!="1",reason="requires MailHog service")
def test_real_smtp_delivery_and_registration(tmp_path,monkeypatch):
    monkeypatch.setenv("HCMUS_PRODUCT_DB_PATH",str(tmp_path/"mailhog.sqlite3"))
    monkeypatch.setenv("HCMUS_OTP_SECRET","mailhog-test-only-"+"x"*32)
    monkeypatch.setenv("SMTP_MODE","mailhog")
    monkeypatch.setenv("SMTP_HOST","127.0.0.1")
    monkeypatch.setenv("SMTP_PORT","1025")
    monkeypatch.delenv("SMTP_USERNAME",raising=False)
    with TestClient(app) as c:
        email="mailhog-test@example.test"
        r=c.post("/product/auth/register/code",json={"email":email})
        assert r.status_code==200,r.text
        code=None
        for _ in range(30):
            items=httpx.get("http://127.0.0.1:8025/api/v2/messages",timeout=3).json()["items"]
            for item in items:
                headers=item["Content"]["Headers"]
                if email in str(headers.get("To",[])):
                    m=re.search(r"(?<!\d)\d{6}(?!\d)",item["Content"]["Body"])
                    if m:code=m.group();break
            if code:break
            time.sleep(.2)
        assert code,"OTP email did not arrive"
        r=c.post("/product/auth/register",json={"email":email,"username":"mailhogtest","password":"Mailhog7!","code":code})
        assert r.status_code==200,r.text
