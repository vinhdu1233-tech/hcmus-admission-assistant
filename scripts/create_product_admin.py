"""Create a pre-provisioned admin; password entered locally, never committed."""
import argparse,getpass
from src.product_auth import create_admin
from src.product_db import db
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--email")
    p.add_argument("--username")
    p.add_argument("--recover-admin",type=int,help="Local operator recovery for a locked admin only")
    a=p.parse_args()
    if a.recover_admin is not None:
        with db(True) as c:
            n=c.execute("UPDATE users SET failed=0,lock_round=0,locked_until=0,hard_locked=0 WHERE id=? AND role='admin'",(a.recover_admin,)).rowcount
        if not n:raise SystemExit("Admin not found")
        print("Admin recovered by local operator.");return
    if not a.email or not a.username:p.error("--email and --username are required")
    pw=getpass.getpass("Admin password: ")
    if pw!=getpass.getpass("Confirm password: "):raise SystemExit("Passwords differ.")
    create_admin(a.email,a.username,pw);print("Admin created.")
if __name__=="__main__":main()
