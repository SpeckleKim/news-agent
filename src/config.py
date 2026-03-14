"""설정 로드: config.yaml + 환경변수 치환."""
import os
from pathlib import Path
from typing import Any, List, Optional

import yaml
from dotenv import load_dotenv

load_dotenv()


def _env(key: str) -> Optional[str]:
    return os.environ.get(key)


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        return _default_config()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _resolve_env(raw)


def _resolve_env(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _resolve_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env(x) for x in obj]
    if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        key = obj[2:-1].strip()
        return _env(key) or obj
    return obj


def _default_config() -> dict:
    return {
        "schedule": {"interval_minutes": 60},
        "sources": [],
        "google_ai": {"api_key_env": "GOOGLE_AI_API_KEY", "model": "gemini-2.0-flash"},
        "storage": {"path": "./data/news.db"},
        "web": {"password_env": "WEB_PASSWORD", "session_ttl_hours": 168},
        "dedup": {"title_similarity_threshold": 0.88, "use_embedding": False},
    }


def get_api_key(config: dict, env_key_name: str) -> Optional[str]:
    """config 내 api_key_env 필드로 환경변수 키 이름을 찾고, 해당 값을 반환."""
    if isinstance(env_key_name, str) and env_key_name:
        return _env(env_key_name)
    return None
