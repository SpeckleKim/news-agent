"""RSS 수집기."""
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

import feedparser

from .base import BaseCollector, RawArticle
from .fetch_article import fetch_article_body


class RSSCollector(BaseCollector):
    def __init__(self, url: str, name: str = "", max_entries: int = 100):
        self.url = url
        self.name = name or urlparse(url).netloc or "RSS"
        self.max_entries = max(1, min(max_entries, 200))  # 소스당 최대 200건

    def collect(self, keywords: list = None, since: Optional[datetime] = None) -> List[RawArticle]:
        results = []
        try:
            parsed = feedparser.parse(self.url)
        except Exception:
            return results
        for entry in getattr(parsed, "entries", [])[: self.max_entries]:
            link = entry.get("link") or ""
            if not link:
                continue
            title = entry.get("title") or ""
            summary = ""
            if hasattr(entry, "summary"):
                summary = getattr(entry, "summary", "") or ""
            elif hasattr(entry, "description"):
                summary = getattr(entry, "description", "") or ""
            published = None
            for k in ("published_parsed", "updated_parsed"):
                if hasattr(entry, k) and getattr(entry, k):
                    try:
                        from time import struct_time
                        t = getattr(entry, k)
                        if isinstance(t, struct_time):
                            published = datetime(*t[:6])
                    except Exception:
                        pass
                    break
            if since is not None and published is not None:
                pub_utc = published.astimezone(timezone.utc).replace(tzinfo=None) if published.tzinfo else published.replace(tzinfo=None)
                since_utc = since.astimezone(timezone.utc).replace(tzinfo=None) if since.tzinfo else since
                if pub_utc < since_utc:
                    continue
            # 링크가 있으면 해당 URL로 들어가 본문 추출. 타임아웃/실패 시 body는 RSS summary(기본값) 유지.
            body_snippet = summary
            fetched = fetch_article_body(link)
            if fetched and len(fetched.strip()) > 150:
                body_snippet = fetched.strip()
            results.append(RawArticle(
                url=link,
                title=title,
                body_snippet=body_snippet,
                source=self.name,
                published_at=published,
            ))
        return results
