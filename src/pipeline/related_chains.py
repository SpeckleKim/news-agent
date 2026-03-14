"""수집·저장 후 연관 뉴스 체인(related_chains) 자동 등록.

카테고리별로 기사·그룹을 묶어 시간순 체인을 만들고, related_chains 테이블에 저장한다.
클릭 시 상세 페이지에서 '관련 뉴스 히스토리'로 표시된다.
"""
import hashlib
import logging
from collections import defaultdict
from datetime import datetime

from src.models import RelatedChain
from src.storage.repository import Repository

logger = logging.getLogger(__name__)


def _safe_chain_id(category: str) -> str:
    """카테고리 문자열로 고유한 체인 ID 생성."""
    label = (category or "기타").strip()
    h = hashlib.sha256(label.encode("utf-8")).hexdigest()[:12]
    return "chain_" + h


def build_related_chains(repo: Repository) -> None:
    """DB의 기사·그룹을 카테고리별·시간순으로 묶어 related_chains에 등록한다."""
    repo.delete_all_chains()

    articles = repo.list_articles_for_feed(limit=5000, offset=0)
    groups = repo.list_groups_for_feed(limit=5000, offset=0)

    buckets = defaultdict(list)
    for a in articles:
        cat = (a.category or "").strip() or "기타"
        buckets[cat].append((a.id, a.published_at))
    for g in groups:
        cat = (g.category or "").strip() or "기타"
        buckets[cat].append((g.id, g.published_at))

    now = datetime.utcnow()
    inserted = 0
    for category, items in buckets.items():
        if len(items) < 2:
            continue
        def sort_key(x):
            pt = x[1]
            if pt is None:
                return ("", "")
            return (pt.isoformat(), "")

        items.sort(key=sort_key)
        ids = [x[0] for x in items]
        chain_id = _safe_chain_id(category)
        ch = RelatedChain(
            id=chain_id,
            article_ids=ids,
            topic_label=category,
            created_at=now,
            updated_at=now,
        )
        repo.insert_chain(ch)
        inserted += 1

    logger.info("Related chains built: %s chains for %s categories", inserted, len(buckets))
