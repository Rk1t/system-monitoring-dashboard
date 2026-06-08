import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import OrganizationMember, User


security = HTTPBearer(auto_error=False)
JWT_SECRET = os.getenv("SYSTEM_MONITOR_JWT_SECRET", "change-this-secret-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 8 * 60


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return f"pbkdf2_sha256${salt}${password_hash.hex()}"


def generate_secret_token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(24)}"


def token_prefix(token: str) -> str:
    parts = token.split("_")
    if len(parts) < 3:
        return token[:16]

    prefix = parts[0] + "_" + parts[1] + "_" + parts[2]
    return prefix[:32]


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, password_hash = stored_hash.split("$", 2)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return hmac.compare_digest(candidate.hex(), password_hash)


def create_access_token(user: User) -> str:
    expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    header = {
        "alg": JWT_ALGORITHM,
        "typ": "JWT",
    }
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "exp": int(expires_at.timestamp()),
    }

    header_json = json.dumps(header)
    payload_json = json.dumps(payload)

    header_part = _base64url_encode(header_json.encode("utf-8"))
    payload_part = _base64url_encode(payload_json.encode("utf-8"))

    signing_text = header_part + "." + payload_part
    signing_input = signing_text.encode("ascii")

    secret = JWT_SECRET.encode("utf-8")
    signature_bytes = hmac.new(secret, signing_input, hashlib.sha256).digest()
    signature_part = _base64url_encode(signature_bytes)

    return header_part + "." + payload_part + "." + signature_part


def decode_access_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header_part = parts[0]
        payload_part = parts[1]
        signature_part = parts[2]

        signing_text = header_part + "." + payload_part
        signing_input = signing_text.encode("ascii")

        secret = JWT_SECRET.encode("utf-8")
        expected_signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
        actual_signature = _base64url_decode(signature_part)

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise ValueError("Invalid signature")

        payload_bytes = _base64url_decode(payload_part)
        payload = json.loads(payload_bytes)

        token_expires_at = int(payload.get("exp", 0))
        now = int(datetime.utcnow().timestamp())

        if token_expires_at < now:
            raise ValueError("Token expired")
        return payload
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истекший token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    return user


def user_organization_ids(db: Session, user: User) -> list[int]:
    rows = db.query(OrganizationMember.organization_id).filter(OrganizationMember.user_id == user.id).all()
    organization_ids = []
    for row in rows:
        organization_ids.append(row[0])
    return organization_ids


def user_role_for_organization(db: Session, user: User, organization_id: int | None) -> str | None:
    if organization_id is None:
        return None
    membership = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user.id, OrganizationMember.organization_id == organization_id)
        .first()
    )
    if membership:
        return membership.role
    return None


def get_user_org_role(db: Session, user: User, organization_id: int | None) -> str | None:
    return user_role_for_organization(db, user, organization_id)


def require_org_role(db: Session, user: User, organization_id: int | None, allowed_roles: set[str]) -> str:
    role = user_role_for_organization(db, user, organization_id)
    if role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return role


def require_org_admin_or_owner(db: Session, user: User, organization_id: int | None) -> str:
    return require_org_role(db, user, organization_id, {"owner", "admin"})


def primary_writable_organization_id(db: Session, user: User) -> int:
    membership = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user.id, OrganizationMember.role.in_(["owner", "admin"]))
        .order_by(OrganizationMember.organization_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет организации с правами записи")
    return membership.organization_id
