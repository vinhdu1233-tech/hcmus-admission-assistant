"""OTP email, bcrypt credentials, opaque sessions and account lock policy."""
from __future__ import annotations
import hashlib,hmac,os,re,secrets,smtplib,ssl,time
from email.message import EmailMessage
import bcrypt
from fastapi import APIRouter,HTTPException,Request,Response
from pydantic import BaseModel,Field,StrictStr
from src.product_db import db
router=APIRouter(prefix="/product")
COOKIE="hcmus_auth"
OTP_TTL=600
OTP_COOLDOWN=60
SESSION_TTL=8*3600
LOCK_SECONDS=15*60
DUMMY=bcrypt.hashpw(b"not-an-account-password",bcrypt.gensalt(rounds=12))

def error(status,detail):raise HTTPException(status,detail)
def email_value(s):
    s=s.strip().lower()
    if len(s)>254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}",s):
        error(400,"Email không hợp lệ.")
    return s
def username_value(s):
    s=s.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}",s):
        error(400,"Username: 3–32 ký tự chữ, số, dấu chấm, gạch ngang hoặc gạch dưới.")
    return s
def password_value(s):
    if len(s)<7 or len(s.encode("utf-8"))>72 or not re.search(r"[A-Z]",s) or not re.search(r"[0-9]",s) or not any(not ch.isalnum() and not ch.isspace() and ch.isprintable() for ch in s) or any(x.isspace() or not x.isprintable() for x in s):
        error(400,"Mật khẩu ít nhất 7 ký tự, có chữ in hoa, số, ký tự đặc biệt; không có khoảng trắng, tối đa 72 byte.")
    return s
def password_hash(s):return bcrypt.hashpw(password_value(s).encode(),bcrypt.gensalt(rounds=12)).decode()
def token_hash(s):return hashlib.sha256(s.encode()).hexdigest()
def otp_digest(email,purpose,code):
    key=os.getenv("HCMUS_OTP_SECRET","")
    if len(key)<32:error(503,"Dịch vụ OTP chưa được cấu hình.")
    return hmac.new(key.encode(),f"{email}|{purpose}|{code}".encode(),hashlib.sha256).hexdigest()
def send_otp(email,code,purpose):
    msg=EmailMessage()
    msg["From"]=os.getenv("SMTP_FROM","guide@example.test")
    msg["To"]=email
    msg["Subject"]="HCMUS Guide — mã xác minh"
    msg.set_content(f"Mã xác minh của bạn: {code}\nCó hiệu lực 10 phút. Không chia sẻ mã này với người khác.")
    mode=os.getenv("SMTP_MODE","mailhog")
    host=os.getenv("SMTP_HOST","127.0.0.1")
    port=int(os.getenv("SMTP_PORT","1025"))
    if mode not in ("mailhog","starttls","ssl"):raise ValueError("invalid SMTP_MODE")
    client=(smtplib.SMTP_SSL(host,port,timeout=8,context=ssl.create_default_context()) if mode=="ssl" else smtplib.SMTP(host,port,timeout=8))
    with client:
        if mode=="starttls":client.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USERNAME"):
            if mode=="mailhog":raise ValueError("do not send SMTP credentials over plaintext")
            client.login(os.environ["SMTP_USERNAME"],os.environ["SMTP_PASSWORD"])
        client.send_message(msg)
def issue_otp(email,purpose):
    now=time.time()
    code=f"{secrets.randbelow(1000000):06d}"
    digest=otp_digest(email,purpose,code)
    with db(True) as c:
        c.execute("DELETE FROM otp_sends WHERE sent_at<?",(now-3600,))
        user=c.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
        if (purpose=="register" and user) or (purpose=="reset" and not user):
            return {"ok":True,"message":"Nếu email phù hợp, mã sẽ được gửi."}
        counts=c.execute("SELECT COUNT(*) FROM otp_sends WHERE email=?",(email,)).fetchone()[0]
        recent=c.execute("SELECT MAX(sent_at) FROM otp_sends WHERE email=?",(email,)).fetchone()[0]
        if counts>=5 or (recent is not None and recent>now-OTP_COOLDOWN):
            error(429,"Vui lòng đợi trước khi yêu cầu mã mới.")
        if c.execute("SELECT COUNT(*) FROM otp_sends").fetchone()[0]>=100:
            error(429,"Dịch vụ email đang bận. Vui lòng thử lại sau.")
        c.execute("INSERT INTO otp_sends VALUES (?,?)",(email,now))
        c.execute("""INSERT INTO otps(email,purpose,digest,expires,attempts,sent_at) VALUES (?,?,?,?,0,?)
          ON CONFLICT(email,purpose) DO UPDATE SET digest=excluded.digest,expires=excluded.expires,attempts=0,sent_at=excluded.sent_at""",
          (email,purpose,digest,now+OTP_TTL,now))
    try:send_otp(email,code,purpose)
    except Exception:
        with db(True) as c:c.execute("DELETE FROM otps WHERE email=? AND purpose=? AND digest=?",(email,purpose,digest))
        error(503,"Không gửi được email. Kiểm tra dịch vụ SMTP.")
    return {"ok":True,"message":"Nếu email phù hợp, mã sẽ được gửi."}
def consume_otp(c,email,purpose,code):
    row=c.execute("SELECT * FROM otps WHERE email=? AND purpose=?",(email,purpose)).fetchone()
    if not row or row["expires"]<=time.time() or row["attempts"]>=5:return False
    valid=re.fullmatch(r"[0-9]{6}",code) and hmac.compare_digest(row["digest"],otp_digest(email,purpose,code))
    if valid:c.execute("DELETE FROM otps WHERE email=? AND purpose=?",(email,purpose))
    else:c.execute("UPDATE otps SET attempts=attempts+1 WHERE email=? AND purpose=?",(email,purpose))
    return bool(valid)
def user_for(request):
    token=request.cookies.get(COOKIE,"")
    if not token or len(token)>128:return None
    with db() as c:
        row=c.execute("""SELECT u.id,u.email,u.username,u.role FROM sessions s JOIN users u ON u.id=s.user_id
          WHERE s.token_hash=? AND s.expires>? AND u.hard_locked=0 AND u.locked_until<=?""",(token_hash(token),time.time(),time.time())).fetchone()
    return dict(row) if row else None
def require_user(request):
    user=user_for(request)
    if not user:error(401,"Bạn cần đăng nhập.")
    return user
def require_admin(request):
    user=require_user(request)
    if user["role"]!="admin":error(403,"Chỉ Admin được phép truy cập.")
    return user
def cookie_secure():return os.getenv("COOKIE_SECURE","0")=="1"
def new_session(c,uid):
    token=secrets.token_urlsafe(32)
    c.execute("DELETE FROM sessions WHERE expires<=?",(time.time(),))
    c.execute("INSERT INTO sessions VALUES (?,?,?)",(token_hash(token),uid,time.time()+SESSION_TTL))
    return token
def create_admin(email,username,password):
    email=email_value(email);username=username_value(username);hashed=password_hash(password)
    with db(True) as c:
        c.execute("INSERT INTO users(email,username,password_hash,role,created_at) VALUES (?,?,?,'admin',?)",(email,username,hashed,time.time()))
def unlock_account(uid):
    with db(True) as c:
        n=c.execute("UPDATE users SET failed=0,lock_round=0,locked_until=0,hard_locked=0 WHERE id=?",(uid,)).rowcount
    if not n:error(404,"Không tìm thấy tài khoản.")
class EmailIn(BaseModel):
    email:StrictStr=Field(max_length=254)
class Registration(EmailIn):
    username:StrictStr=Field(max_length=32)
    password:StrictStr=Field(max_length=128)
    code:StrictStr=Field(max_length=20)
class Reset(EmailIn):
    password:StrictStr=Field(max_length=128)
    code:StrictStr=Field(max_length=20)
class Login(BaseModel):
    identifier:StrictStr=Field(max_length=254)
    password:StrictStr=Field(max_length=128)
@router.post("/auth/register/code")
def register_code(body:EmailIn):return issue_otp(email_value(body.email),"register")
@router.post("/auth/register")
def register(body:Registration):
    email=email_value(body.email);name=username_value(body.username);hashed=password_hash(body.password)
    with db(True) as c:
        valid=consume_otp(c,email,"register",body.code)
        if valid:
            exists=c.execute("SELECT id FROM users WHERE email=? OR username=?",(email,name)).fetchone()
            if not exists:
                c.execute("INSERT INTO users(email,username,password_hash,created_at) VALUES (?,?,?,?)",(email,name,hashed,time.time()))
            else:valid=False
    if not valid:error(400,"Mã không hợp lệ/hết hạn hoặc tài khoản đã tồn tại.")
    return {"ok":True}
@router.post("/auth/reset/code")
def reset_code(body:EmailIn):return issue_otp(email_value(body.email),"reset")
@router.post("/auth/reset")
def reset(body:Reset):
    email=email_value(body.email);hashed=password_hash(body.password)
    with db(True) as c:
        valid=consume_otp(c,email,"reset",body.code)
        user=c.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
        if valid and user:
            c.execute("UPDATE users SET password_hash=? WHERE id=?",(hashed,user["id"]))
            c.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
        else:valid=False
    if not valid:error(400,"Mã không hợp lệ hoặc hết hạn.")
    return {"ok":True,"message":"Đã đổi mật khẩu. Việc đổi mật khẩu không mở khóa tài khoản."}
@router.post("/auth/login")
def login(body:Login,response:Response):
    now=time.time()
    password=body.password.encode()
    if len(password)>72:error(401,"Thông tin đăng nhập không đúng.")
    identifier=body.identifier.strip()
    # Hash verification outside write transaction; recheck state/hash before updating.
    with db() as c:
        row=c.execute("SELECT * FROM users WHERE email=? OR username=?",(identifier,identifier)).fetchone()
    matches=bcrypt.checkpw(password,row["password_hash"].encode() if row else DUMMY)
    outcome=401;detail="Thông tin đăng nhập không đúng.";token=None;public=None
    if row:
        with db(True) as c:
            u=c.execute("SELECT * FROM users WHERE id=?",(row["id"],)).fetchone()
            if u["hard_locked"]:
                outcome=423;detail="Tài khoản bị khóa. Liên hệ Admin để mở khóa."
            elif u["locked_until"]>now:
                outcome=423;detail="Tài khoản đang bị khóa 15 phút."
            elif u["password_hash"]!=row["password_hash"]:
                outcome=401
            elif matches:
                c.execute("UPDATE users SET failed=0,locked_until=0 WHERE id=?",(u["id"],))
                token=new_session(c,u["id"])
                public={k:u[k] for k in ("id","username","email","role")}
            else:
                count=u["failed"]+1
                if count>=4:
                    hard=int(u["lock_round"]>=1)
                    c.execute("UPDATE users SET failed=0,lock_round=1,locked_until=?,hard_locked=? WHERE id=?",(0 if hard else now+LOCK_SECONDS,hard,u["id"]))
                    c.execute("DELETE FROM sessions WHERE user_id=?",(u["id"],))
                    outcome=423
                    detail="Tài khoản bị khóa. Liên hệ Admin để mở khóa." if hard else "Sai 4 lần. Tài khoản bị khóa 15 phút."
                else:c.execute("UPDATE users SET failed=? WHERE id=?",(count,u["id"]))
    if not token:error(outcome,detail)
    response.set_cookie(COOKIE,token,max_age=SESSION_TTL,httponly=True,secure=cookie_secure(),samesite="strict",path="/")
    return {"user":public}
@router.get("/auth/me")
def me(request:Request):return {"user":user_for(request)}
class LogoutBody(BaseModel):
    endpoint:StrictStr|None=Field(default=None,max_length=2048)
@router.post("/auth/logout")
def logout(request:Request,response:Response,body:LogoutBody|None=None):
    token=request.cookies.get(COOKIE,"")
    if token:
        with db(True) as c:
            session=c.execute("SELECT user_id FROM sessions WHERE token_hash=?",(token_hash(token),)).fetchone()
            if session and body and body.endpoint:
                c.execute("DELETE FROM push_subscriptions WHERE user_id=? AND endpoint=?",(session["user_id"],body.endpoint))
            c.execute("DELETE FROM sessions WHERE token_hash=?",(token_hash(token),))
    response.delete_cookie(COOKIE,path="/",httponly=True,samesite="strict",secure=cookie_secure())
    return {"ok":True}
