"""세션 쿠키, 비밀번호 검증, 인증 의존성."""
import os
import secrets
import time
from typing import Optional

from fastapi import HTTPException, Request

SESSION_COOKIE = "news_agent_sid"
SESSIONS: dict = {}

SESSION_TTL_HOURS = 168


def _load_web_password() -> str:
    try:
        from src.config import load_config
        cfg = load_config()
        web = cfg.get("web") or {}
        env_key = web.get("password_env") or "WEB_PASSWORD"
        return (os.environ.get("WEB_PASSWORD") or os.environ.get(env_key) or "").strip()
    except Exception:
        return (os.environ.get("WEB_PASSWORD") or "").strip()


def verify_password(password: str) -> bool:
    if not password:
        return False
    expected = _load_web_password()
    return bool(expected and expected == password.strip())


def create_session() -> str:
    sid = secrets.token_urlsafe(32)
    SESSIONS[sid] = {"created": time.time()}
    return sid


def is_valid_session(sid: Optional[str]) -> bool:
    if not sid or sid not in SESSIONS:
        return False
    ttl_sec = SESSION_TTL_HOURS * 3600
    if time.time() - SESSIONS[sid]["created"] > ttl_sec:
        SESSIONS.pop(sid, None)
        return False
    return True


def destroy_session(sid: Optional[str]) -> None:
    SESSIONS.pop(sid, None)


def get_session_id(request: Request) -> Optional[str]:
    return request.cookies.get(SESSION_COOKIE)


def require_auth(request: Request) -> str:
    sid = get_session_id(request)
    if not sid or not is_valid_session(sid):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return sid
