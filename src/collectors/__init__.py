"""수집기 팩토리 및 통합 실행."""
import os
from datetime import datetime, timedelta
from typing import List, Optional

from .base import RawArticle
from .gnews import GNewsCollector
from .rss import RSSCollector


def run_all_collectors(config: dict, max_items: Optional[int] = None) -> List[RawArticle]:
    """config.sources를 순회하며 수집. URL 중복 제거. collect_hours 이내 발행 뉴스만.

    max_items가 주어지면 해당 개수만 모이면 즉시 중단 (테스트/빠른 실행용).
    """
    results = []
    seen_urls = set()
    schedule = config.get("schedule") or {}
    default_collect_hours = int(schedule.get("collect_hours") or 1)
    limit = int(max_items) if (max_items is not None and int(max_items) > 0) else None

    for src in config.get("sources") or []:
        if limit is not None and len(results) >= limit:
            break
        collect_hours = int(src.get("collect_hours") or default_collect_hours)
        since: Optional[datetime] = datetime.utcnow() - timedelta(hours=collect_hours) if collect_hours > 0 else None
        typ = src.get("type")
        if typ == "rss":
            url = src.get("url")
            if not url:
                continue
            name = src.get("name") or ""
            max_entries = int(src.get("max_entries") or src.get("max") or 100)
            coll = RSSCollector(url=url, name=name, max_entries=max_entries)
            for raw in coll.collect(since=since):
                if raw.url not in seen_urls:
                    seen_urls.add(raw.url)
                    results.append(raw)
                    if limit is not None and len(results) >= limit:
                        break
        elif typ == "gnews":
            env_key = src.get("api_key_env")
            api_key = os.environ.get(env_key) if env_key else None
            if not api_key:
                continue
            keywords = src.get("keywords") or []
            max_per_keyword = int(src.get("max") or src.get("max_per_keyword") or 10)
            coll = GNewsCollector(api_key=api_key, keywords=keywords, max_per_keyword=max_per_keyword)
            for raw in coll.collect(since=since):
                if raw.url not in seen_urls:
                    seen_urls.add(raw.url)
                    results.append(raw)
                    if limit is not None and len(results) >= limit:
                        break
    return results
