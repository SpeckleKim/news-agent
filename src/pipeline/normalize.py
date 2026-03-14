"""URL 정규화 및 Article 초안 생성."""
import hashlib
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse

from src.models import Article
from src.collectors.base import RawArticle


def normalize_url(url: str) -> str:
    if not url or not url.strip():
        return ""
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        parsed = urlparse("https://" + url.strip())
    path = parsed.path or "/"
    query = parsed.query
    if query:
        qparams = []
        for part in sorted(query.split("&")):
            if "=" in part:
                k, v = part.split("=", 1)
                k = k.lower()
                if k in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid", "ref"):
                    continue
                qparams.append(f"{k}={v}")
        query = "&".join(sorted(qparams)) if qparams else ""
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", query, ""))


def url_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def raw_to_article(raw: RawArticle, collected_at: Optional[datetime] = None) -> Article:
    norm = normalize_url(raw.url)
    return Article(
        id="",
        url=raw.url,
        url_hash=url_hash(norm),
        title=(raw.title or "").strip() or "제목 없음",
        summary="",
        body_snippet=(raw.body_snippet or "")[:100000],
        source=raw.source or "",
        published_at=raw.published_at,
        collected_at=collected_at or datetime.utcnow(),
        keywords=[],
        category="",
        duplicate_group_id=None,
        version=1,
        importance=None,
    )
