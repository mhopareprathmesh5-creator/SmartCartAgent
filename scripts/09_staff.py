"""Manage store-staff accounts for the admin page.

    python scripts/09_staff.py list
    python scripts/09_staff.py add asha "Asha Patil" staff        # asks for the password
    python scripts/09_staff.py password manager                   # change a password (do this before deploying)
    python scripts/09_staff.py disable staff

Roles: manager (prices, stock, coupons) · staff (stock only).
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common  # noqa: E402,F401  (UTF-8 console)
from sqlalchemy import text  # noqa: E402

from smartcart.auth import ROLES, create_user, hash_password  # noqa: E402
from smartcart.db import get_engine  # noqa: E402


def ask_password() -> str:
    pw = getpass.getpass("New password: ")
    if len(pw) < 8 or pw != getpass.getpass("Repeat: "):
        sys.exit("Passwords must match and be at least 8 characters.")
    return pw


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    with get_engine().begin() as conn:
        if cmd == "list":
            for r in conn.execute(text("SELECT username, full_name, role, is_active FROM staff_users ORDER BY 1")):
                print(f"{r.username:<12} {r.full_name:<20} {r.role:<8} {'active' if r.is_active else 'disabled'}")
        elif cmd == "add" and len(args) == 3 and args[2] in ROLES:
            create_user(conn, args[0], args[1], args[2], ask_password())
            print(f"Added {args[0]} ({args[2]})")
        elif cmd == "password" and len(args) == 1:
            n = conn.execute(text("UPDATE staff_users SET password_hash = :h WHERE username = :u"),
                             {"h": hash_password(ask_password()), "u": args[0]}).rowcount
            print("Password changed" if n else f"No user {args[0]!r}")
        elif cmd == "disable" and len(args) == 1:
            n = conn.execute(text("UPDATE staff_users SET is_active = FALSE WHERE username = :u"), {"u": args[0]}).rowcount
            print("Disabled" if n else f"No user {args[0]!r}")
        else:
            sys.exit(__doc__)


if __name__ == "__main__":
    main()
