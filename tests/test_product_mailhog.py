"""SMTP integration: run with MailHog service. No real emails leave the CI runner."""
import os,re,time
import pytest,httpx
from src.product_db import db
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
                    if m:code=m.group();old_id=item['ID'];break
            if code:break
            time.sleep(.2)
        assert code,"OTP email did not arrive"
        r=c.post("/product/auth/register",json={"email":email,"username":"mailhogtest","password":"Mailhog7!","code":code})
        assert r.status_code==200,r.text
        # Real SMTP reset mail too; bypass only test cooldown, not OTP checks.
        with db(True) as d:d.execute("DELETE FROM otp_sends")
        assert c.post("/product/auth/login",json={"identifier":"mailhogtest","password":"Mailhog7!"}).status_code==200
        assert c.post("/product/auth/reset/code",json={"email":email}).status_code==200
        reset_code=None
        for _ in range(30):
            items=httpx.get("http://127.0.0.1:8025/api/v2/messages",timeout=3).json()["items"]
            for item in items:
                if email in str(item["Content"]["Headers"].get("To",[])):
                    m=re.search(r"(?<!\d)\d{6}(?!\d)",item["Content"]["Body"])
                    if m and item["ID"] != old_id:
                        reset_code=m.group();break
            if reset_code:break
            time.sleep(.2)
        assert reset_code,"Password-reset email did not arrive"
        assert c.post("/product/auth/reset",json={"email":email,"password":"NewMail8!","code":reset_code}).status_code==200
        assert c.get("/product/auth/me").json()["user"] is None
        assert c.post("/product/auth/login",json={"identifier":"mailhogtest","password":"NewMail8!"}).status_code==200
