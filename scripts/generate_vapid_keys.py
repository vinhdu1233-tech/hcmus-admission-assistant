"""Generate a VAPID private PEM outside Git; print only the public key."""
import argparse,base64,os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--file",default="data/processed/vapid-private.pem")
    a=p.parse_args();path=Path(a.file)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        key=serialization.load_pem_private_key(path.read_bytes(),password=None)
    else:
        key=ec.generate_private_key(ec.SECP256R1())
        data=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as f:f.write(data)
    raw=key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    print("VAPID_PUBLIC_KEY="+base64.urlsafe_b64encode(raw).decode().rstrip("="))
    print("VAPID_PRIVATE_KEY="+str(path.resolve()))
    print("Set VAPID_SUBJECT=mailto:your-operator-email and keep the private key file secret.")
if __name__=="__main__":main()
