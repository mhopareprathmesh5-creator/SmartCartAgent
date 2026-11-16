"""Store-staff login and roles for the admin page (Phase II enhancement).

  manager : change prices, stock and coupons
  staff   : change stock only (shelf staff restock; they cannot reprice)

Passwords are stored as PBKDF2-SHA256 hashes (salted, 200k iterations). After login
the server returns a signed token (HMAC-SHA256 over username, role and expiry), sent
back as `Authorization: Bearer <token>`. Standard library only — no extra packages.
The secret comes from ADMIN_TOKEN_SECRET in .env; without it a random secret is made
at start-up (tokens then end when the server restarts, which is fine for a demo).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text

from smartcart.db import get_engine

ITERATIONS = 200_000
TOKEN_HOURS = 12
ROLES = ("manager", "staff")
_SECRET = (os.getenv("ADMIN_TOKEN_SECRET") or secrets.token_hex(32)).encode()

# demo accounts created by scripts/03_seed_database.py (change them for any real use)
DEMO_USERS = [("manager", "Store Manager", "manager", "manager123"),
              ("staff", "Shelf Staff", "staff", "staff123")]


class AuthError(Exception):
    """401: not logged in / bad credentials / expired token."""


class Forbidden(Exception):
    """403: logged in, but the role may not do this."""


@dataclass(frozen=True)
class StaffUser:
    username: str
    full_name: str
    role: str


# ---------------------------------------------------------------- passwords
def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return hmac.compare_digest(test, digest)


# ---------------------------------------------------------------- tokens
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_token(user: StaffUser, now: Optional[float] = None) -> str:
    payload = _b64(json.dumps({"u": user.username, "r": user.role, "n": user.full_name,
                               "exp": int((now or time.time()) + TOKEN_HOURS * 3600)}).encode())
    sig = _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_token(token: str, now: Optional[float] = None) -> StaffUser:
    try:
        payload, sig = token.split(".")
    except ValueError:
        raise AuthError("Malformed token")
    good = _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, good):
        raise AuthError("Invalid token")
    data = json.loads(_unb64(payload))
    if data["exp"] < (now or time.time()):
        raise AuthError("Session expired, please log in again")
    return StaffUser(data["u"], data["n"], data["r"])


# ---------------------------------------------------------------- users
def login(username: str, password: str) -> tuple[StaffUser, str]:
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT username, full_name, role, password_hash, is_active FROM staff_users "
                                "WHERE username = :u"), {"u": username.strip().lower()}).mappings().first()
    if row is None or not row["is_active"] or not verify_password(password, row["password_hash"]):
        raise AuthError("Wrong username or password")
    user = StaffUser(row["username"], row["full_name"], row["role"])
    return user, issue_token(user)


def create_user(conn, username: str, full_name: str, role: str, password: str):
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    conn.execute(text("""INSERT INTO staff_users (username, full_name, role, password_hash)
                         VALUES (:u, :n, :r, :h)"""),
                 {"u": username.lower(), "n": full_name, "r": role, "h": hash_password(password)})


def require(user: StaffUser, *roles: str):
    if user.role not in roles:
        raise Forbidden(f"The {user.role} role cannot do this (needs: {' or '.join(roles)})")
