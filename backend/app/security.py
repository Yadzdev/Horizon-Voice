from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import Account, BrowserSession, Server

_password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=2)
_bearer = HTTPBearer(auto_error=False)


def new_id() -> str:
    return str(uuid.uuid4())


def new_secret(size: int = 32) -> str:
    return secrets.token_urlsafe(size)


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(account_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": account_id,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "jti": new_id(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer)
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise ValueError("missing subject")
        return subject
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada") from exc


def require_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Account:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    account_id = decode_access_token(credentials.credentials)
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=401, detail="Conta não encontrada")
    return account


def server_auth(db: Session = Depends(get_db), x_server_key: str | None = Header(default=None, alias="X-Server-Key")) -> Server:
    if not x_server_key:
        raise HTTPException(status_code=401, detail="Credencial do servidor ausente")
    server = db.query(Server).filter(Server.server_secret_hash == hash_value(x_server_key)).first()
    if server is None or server.status != "active":
        raise HTTPException(status_code=401, detail="Credencial do servidor inválida")
    return server


def get_browser_session(token: str | None, db: Session) -> BrowserSession:
    if not token:
        raise HTTPException(status_code=401, detail="Sessão do navegador ausente")
    session = db.query(BrowserSession).filter(BrowserSession.token_hash == hash_value(token)).first()
    now = datetime.now(timezone.utc)
    if session is None:
        raise HTTPException(status_code=401, detail="Sessão do navegador inválida ou expirada")
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if session.revoked_at is not None or expires_at <= now:
        raise HTTPException(status_code=401, detail="Sessão do navegador inválida ou expirada")
    return session
