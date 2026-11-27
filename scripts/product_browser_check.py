"""Real Chrome + Node proxy + FastAPI + SQLite + MailHog. Local CI only."""
from __future__ import annotations
import time,json,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
import httpx
from playwright.sync_api import sync_playwright,expect
from src.product_auth import create_admin
BASE="http://127.0.0.1:5501"
OUT=Path("product-browser-evidence");OUT.mkdir(exist_ok=True)
def wait_services():
    for i in range(60):
        try:
            assert httpx.get(BASE+"/api/config",timeout=1).json()["mode"]=="api"
            assert httpx.get("http://127.0.0.1:8000/health",timeout=1).status_code==200
            return
        except Exception:time.sleep(.3)
    raise RuntimeError("Services not ready")
def otp_for(address):
    for _ in range(30):
        for x in httpx.get("http://127.0.0.1:8025/api/v2/messages").json()["items"]:
            if address in str(x["Content"]["Headers"].get("To",[])):
                m=re.search(r"(?<!\d)\d{6}(?!\d)",x["Content"]["Body"])
                if m:return m.group()
        time.sleep(.3)
    raise AssertionError("Missing OTP email")
def main():
    wait_services();create_admin("browser-admin@example.test","browseradmin","Browser7!")
    result=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="chrome",headless=True,args=["--no-sandbox"])
        student=browser.new_context(viewport={"width":1440,"height":950})
        page=student.new_page()
        page.goto(BASE+"/portal.html#account",wait_until="domcontentloaded")
        expect(page.locator("#login-form")).to_be_visible()
        page.locator('[data-auth-tab="register"]').click()
        form=page.locator("#register-form")
        for name,val in {"email":"browser-student@example.test","username":"browserstudent","password":"Browser7!"}.items():form.locator(f'[name="{name}"]').fill(val)
        form.locator('[data-send-code="register"]').click()
        expect(page.locator("#message")).to_contain_text("mã")
        form.locator('[name="code"]').fill(otp_for("browser-student@example.test"))
        form.locator('button[type=submit]').click()
        expect(page.locator("#login-form")).to_be_visible()
        result.append("registration_email_otp")
        login=page.locator("#login-form")
        login.locator('[name=identifier]').fill("browserstudent");login.locator('[name=password]').fill("Browser7!");login.locator('button[type=submit]').click()
        expect(page.locator("#calendar")).to_be_visible()
        expect(page.locator("#nav-dashboard")).to_be_hidden()
        expect(page.locator("#month-grid .day")).to_have_count(42)
        result.append("student_login_calendar")
        page.locator("#year").select_option("2026");page.locator("#method").select_option("1a")
        expect(page.locator("#year-events")).to_contain_text("phương thức 1a")
        page.locator("#year-events .event-row").first.click()
        expect(page.locator("#event-detail")).to_contain_text("Mở thông báo chính thức")
        page.locator('[data-close="detail-dialog"]').click()
        result.append("official_calendar_filter")
        page.locator("#method").select_option("all")
        common=page.locator("#year-events .event-row").filter(has_text="Dự kiến tra cứu kết quả trúng tuyển")
        expect(common).to_have_count(1)
        common.click()
        expect(page.locator("#event-detail")).to_contain_text("1a, 1b, 2")
        page.locator("#event-detail").get_by_role("button",name="Phương thức 1b",exact=True).click()
        expect(page.locator("#event-detail")).to_contain_text("Nhắc lịch riêng")
        page.locator('[data-close="detail-dialog"]').click()
        page.locator("#method").select_option("1a")
        result.append("shared_calendar_event_grouping")
        for view in ("week","day","agenda"):
            page.locator("#calendar-view").select_option(view)
            expect(page.locator("#alternate-view")).to_be_visible()
            expect(page.locator("#month-grid")).to_be_hidden()
        page.locator("#calendar-view").select_option("month")
        page.locator("#calendar-search").fill("unmatchable-event-name")
        expect(page.locator("#month-grid .event-chip")).to_have_count(0)
        page.locator("#calendar-search").fill("")
        result.append("calendar_views_and_search")
        page.locator("#new-event").click()
        form=page.locator("#personal-form")
        future=datetime.now(timezone(timedelta(hours=7)))+timedelta(days=12)
        form.locator('[name=title]').fill("Personal browser reminder")
        form.locator('[name=start]').fill(future.strftime("%Y-%m-%dT%H:%M"))
        form.locator('[name=end]').fill((future+timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"))
        form.locator('button[type=submit]').click()
        expect(page.locator("#event-dialog")).to_be_hidden()
        events=student.request.get(BASE+"/api/product/calendar?year=2026&method=all").json()["events"]
        e=next(x for x in events if x["title"]=="Personal browser reminder")
        # Navigate to the personal event month and exercise the actual reminder UI.
        target=future.date().isoformat()
        for _ in range(24):
            # Calendar starts in June (the selected historical official method).
            label=page.locator("#month-label").inner_text()
            m=re.search(r"Tháng (\d+), (\d+)",label)
            if (int(m.group(2)),int(m.group(1)))==(future.year,future.month):break
            if (int(m.group(2)),int(m.group(1)))<(future.year,future.month):page.locator("#next").click()
            else:page.locator("#prev").click()
        page.locator(".event-chip").filter(has_text="Personal browser reminder").first.click()
        detail=page.locator("#event-detail")
        for edge in ("start","end"):
            for offset in ("7","4"):detail.locator(f'input[name="{edge}"][value="{offset}"]').check()
        detail.get_by_role("button",name="Lưu nhắc lịch").click()
        expect(page.locator("#detail-dialog")).to_be_hidden()
        actual=student.request.get(BASE+"/api/product/calendar?year=2026&method=all").json()["reminders"]
        assert {(x["edge"],x["days_before"]) for x in actual if x["event_id"]==e["id"]}=={("start",7),("start",4),("end",7),("end",4)}
        result.append("personal_event_and_start_end_reminders")
        assert student.request.get(BASE+"/api/product/admin/questions").status==403
        result.append("student_admin_api_denied")
        page.screenshot(path=str(OUT/"calendar.png"),full_page=True)
        page.goto(BASE+"/",wait_until="domcontentloaded")
        expect(page.locator(".desktop-nav")).to_contain_text("Tài khoản")
        page.locator("#floating-chat").click();page.locator("#question").fill("Ngành nào xét A01 năm 2026?")
        with page.expect_response(lambda r:r.url.endswith("/api/chat"),timeout=20000) as rr:page.locator("#send-button").click()
        assert rr.value.status==200
        result.append("logged_in_chat")
        page.locator("#close-modal").click()
        page.locator("#planner-year").select_option("2026")
        page.locator("#planner-method").select_option("1a")
        page.on("dialog",lambda dialog:dialog.accept())
        page.get_by_role("button",name="Liên kết với lịch tài khoản").click()
        expect(page.locator("#planner-saved")).to_contain_text("LIÊN KẾT")
        page.goto(BASE+"/portal.html#calendar",wait_until="domcontentloaded")
        page.locator("#year").select_option("2026")
        page.locator("#method").select_option("1a")
        expect(page.locator("#linked-checklist")).to_contain_text("1a")
        result.append("checklist_calendar_link")
        admin=browser.new_context(viewport={"width":1440,"height":950})
        ap=admin.new_page();ap.goto(BASE+"/portal.html#account",wait_until="domcontentloaded")
        af=ap.locator("#login-form");expect(af).to_be_visible()
        af.locator('[name=identifier]').fill("browseradmin");af.locator('[name=password]').fill("Browser7!");af.locator('button[type=submit]').click()
        expect(ap.locator("#dashboard")).to_be_visible()
        expect(ap.locator("#questions")).to_contain_text("browserstudent")
        expect(ap.locator("#questions")).to_contain_text("A01")
        ap.locator("#questions button").first.click();expect(ap.locator("#question-detail")).to_contain_text("A01")
        ap.locator('[data-close="question-dialog"]').click()
        result.append("admin_dashboard_question_detail")
        ap.screenshot(path=str(OUT/"dashboard.png"),full_page=True)
        ap.goto(BASE+"/",wait_until="domcontentloaded")
        expect(ap.locator(".desktop-nav")).to_contain_text("Dashboard")
        result.append("role_based_main_navigation")
        # Exercise three actual proposal buttons in student browser.
        page.goto(BASE+"/portal.html#calendar",wait_until="domcontentloaded")
        page.locator("#year").select_option("2026");page.locator("#method").select_option("1a")
        page.locator("#follow-method").check()
        expect(page.locator("#message")).to_contain_text("theo dõi")
        start=(future+timedelta(days=5)).isoformat();end=(future+timedelta(days=7)).isoformat()
        payload={"title":"TEST consent browser","year":future.year,"method":"1a","start":start,"end":end,"source_url":"https://tuyensinh.hcmus.edu.vn/2026-thong-bao-mo-cong-dang-ky-phuong-thuc-1a/"}
        r=admin.request.post(BASE+"/api/product/admin/calendar",data=payload);assert r.ok,r.text()
        payload["id"]=r.json()["id"]
        page.reload(wait_until="domcontentloaded")
        proposal=page.locator(".proposal").filter(has_text="TEST consent browser").first
        expect(proposal).to_contain_text("Chờ xác nhận")
        proposal.locator('[data-decision=deferred]').click();expect(proposal).to_contain_text("Để sau")
        proposal.locator('[data-decision=accepted]').click();expect(proposal).to_contain_text("Đã đồng ý")
        payload["end"]=(future+timedelta(days=9)).isoformat()
        r=admin.request.post(BASE+"/api/product/admin/calendar",data=payload);assert r.ok,r.text()
        page.reload(wait_until="domcontentloaded");proposal=page.locator(".proposal").filter(has_text="TEST consent browser").first
        proposal.locator('[data-decision=rejected]').click()
        expect(page.locator(".proposal").filter(has_text="TEST consent browser").filter(has_text="Đã từ chối")).to_be_visible()
        expect(page.locator("#personal-plans")).to_contain_text("Kế hoạch cũ")
        page.screenshot(path=str(OUT/"calendar-approval.png"),full_page=True)
        result.append("calendar_proposal_defer_accept_reject")
        student.close();admin.close();browser.close()
    (OUT/"results.json").write_text(json.dumps({"passed":result,"total":len(result)},indent=2))
    print("BROWSER_PRODUCT_RESULTS",json.dumps(result))
if __name__=="__main__":main()
