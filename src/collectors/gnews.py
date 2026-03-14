"""GNews API 수집기 (gnews.io)."""
from datetime import datetime
from typing import List, Optional

import requests

from .base import BaseCollector, RawArticle


class GNewsCollector(BaseCollector):
    def __init__(self, api_key: str, keywords: list = None, max_per_keyword: int = 10):
        self.api_key = api_key
        self.keywords = keywords or []
        # gnews.io: Free=10, Essential=25, Business=50, Enterprise=100
        self.max_per_keyword = max(1, min(max_per_keyword, 100))

    def collect(self, keywords: list = None, since: Optional[datetime] = None) -> List[RawArticle]:
        kws = keywords or self.keywords
        if not self.api_key or not kws:
            return []
        results = []
        seen = set()
        now = datetime.utcnow()
        params = {"q": kws[0], "token": self.api_key, "lang": "ko", "max": self.max_per_keyword}
        if since is not None:
            params["from"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            params["to"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        for q in kws:
            try:
                p = {**params, "q": q}
                r = requests.get(
                    "https://gnews.io/api/v4/search",
                    params=p,
                    timeout=15,
                )
                if r.status_code != 200:
                    continue
                data = r.json()
            except Exception:
                continue
            for art in data.get("articles") or []:
                url = art.get("url") or ""
                if url in seen:
                    continue
                seen.add(url)
                pub = art.get("published")
                try:
                    published = datetime.fromisoformat(pub.replace("Z", "+00:00")) if pub else None
                except Exception:
                    published = None
                content = (art.get("content") or art.get("description") or "")[:100000]
                results.append(RawArticle(
                    url=url,
                    title=art.get("title") or "",
                    body_snippet=content,
                    source=art.get("source", {}).get("name", "GNews"),
                    published_at=published,
                ))
        return results
