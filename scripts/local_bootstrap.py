"""Persist development-only OTP/VAPID secrets in the Docker data volume."""
import os,secrets,base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
def _write_new(path,data):
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"wb") as f:f.write(data)
    except FileExistsError:pass
def configure():
    if os.getenv("HCMUS_LOCAL_BOOTSTRAP")!="1":return
    directory=Path("/data/local-secrets");directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    secret=directory/"otp-secret"
    _write_new(secret,secrets.token_hex(32).encode())
    if not os.getenv("HCMUS_OTP_SECRET"):os.environ["HCMUS_OTP_SECRET"]=secret.read_text().strip()
    if not os.getenv("VAPID_PUBLIC_KEY") and not os.getenv("VAPID_PRIVATE_KEY"):
        private=directory/"vapid.pem"
        key=ec.generate_private_key(ec.SECP256R1())
        _write_new(private,key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        key=serialization.load_pem_private_key(private.read_bytes(),password=None)
        raw=key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        os.environ["VAPID_PUBLIC_KEY"]=base64.urlsafe_b64encode(raw).decode().rstrip("=")
        os.environ["VAPID_PRIVATE_KEY"]=str(private)
    if not os.getenv("VAPID_SUBJECT"):os.environ["VAPID_SUBJECT"]="mailto:guide@example.test"
