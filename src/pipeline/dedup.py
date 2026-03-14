"""중복 탐지 및 통합 그룹 생성/재병합."""
import logging
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from src.models import Article, DuplicateGroup
from src.storage.repository import Repository

logger = logging.getLogger(__name__)


def _jaccard_char(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_set = set(a.replace(" ", ""))
    b_set = set(b.replace(" ", ""))
    if not a_set and not b_set:
        return 1.0
    inter = len(a_set & b_set)
    union = len(a_set | b_set)
    return inter / union if union else 0.0


def _word_set(text: str) -> set:
    """공백·구두점 기준 토큰 (한국어 제목에서 '김시현', '골프' 등 공통어 추출)."""
    t = (text or "").strip()
    tokens = re.findall(r"[^\s,·\-\[\]()]+", t)
    return set(t for t in tokens if len(t) >= 2)


def _normalize_title_for_similarity(title: str) -> str:
    """유사도 계산 전 제목 정규화: [포토]/[카드] 접두사, ' - 출처' 접미사 제거해 같은 이벤트 묶기."""
    t = (title or "").strip()
    t = re.sub(r"^\[포토\]\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^\[카드\]\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*-\s*[^\s\-]+\.?(com|co\.kr|net|뉴스|네이트|매일경제|edaily)[^\s]*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*-\s*[^\s\-]+$", "", t).strip()
    return t or title


def _title_similarity(t1: str, t2: str) -> float:
    """제목 유사도. 정규화 제목 + 원문 각각 비교해 최대값 사용 (같은 사건, 다른 매체 제목도 묶이도록)."""
    raw1, raw2 = (t1 or "").strip(), (t2 or "").strip()
    if raw1 == raw2:
        return 1.0
    if len(raw1) < 3 or len(raw2) < 3:
        return 0.0
    norm1, norm2 = _normalize_title_for_similarity(raw1), _normalize_title_for_similarity(raw2)
    if norm1 == norm2:
        return 1.0

    def _score(a: str, b: str) -> float:
        scores = [_jaccard_char(a, b)]
        w1, w2 = _word_set(a), _word_set(b)
        if w1 and w2:
            inter = len(w1 & w2)
            union = len(w1 | w2)
            scores.append(inter / union if union else 0.0)
        scores.append(SequenceMatcher(None, a, b).ratio())
        return max(scores)

    return max(_score(raw1, raw2), _score(norm1, norm2))


def run_dedup(
    repo: Repository,
    new_articles: List[Article],
    threshold: float = 0.88,
    use_llm_event_identifier: bool = False,
    llm_same_event_client=None,
    llm_min_interval: float = 1.0,
    gray_min: float = 0.0,
    gray_max: float = 0.0,
) -> Tuple[List[Article], List[Article], List[DuplicateGroup]]:
    """
    새 기사 목록에 대해 URL 중복 시 갱신, 같은 내용인지 제목 또는 LLM 사건 식별자로 그룹 매칭.
    gray_min < gray_max이고 llm_same_event_client이 있으면, 유사도가 [gray_min, gray_max)일 때 are_same_event로 최종 판단.
    """
    to_insert: List[Article] = []
    to_update: List[Article] = []
    groups_updated: List[DuplicateGroup] = []
    use_gray = (
        use_llm_event_identifier
        and llm_same_event_client
        and gray_min < gray_max
        and gray_max > 0
    )
    if use_llm_event_identifier and hasattr(repo, "get_recent_titles_and_identifiers"):
        recent = repo.get_recent_titles_and_identifiers(days=14)
        recent_titles = {aid: (etitle, eident) for aid, etitle, eident in recent}
    else:
        recent = repo.get_recent_titles(days=14)
        recent_titles = {aid: (title, None) for aid, title in recent}
    current_batch: List[Tuple[str, str, Optional[str], Article]] = []

    def _ref(art: Article) -> str:
        return (getattr(art, "event_identifier", None) or "").strip() or (art.title or "")

    def _ref_recent(eid: str) -> str:
        etitle, eident = recent_titles.get(eid, ("", None))
        return (eident or "").strip() or etitle

    def _same_event(art_a: Article, art_b: Article) -> bool:
        if not use_gray or not llm_same_event_client:
            return False
        from src.pipeline.gemini_processor import are_same_event
        s_a = (art_a.summary or "") or (getattr(art_a, "body_snippet", "") or "")
        s_b = (art_b.summary or "") or (getattr(art_b, "body_snippet", "") or "")
        return are_same_event(
            llm_same_event_client,
            art_a.title or "",
            s_a,
            art_b.title or "",
            s_b,
            llm_min_interval,
        )

    for a in new_articles:
        existing = repo.get_by_url_hash(a.url_hash)
        if existing:
            a.id = existing.id
            a.version = existing.version + 1
            a.summary = a.summary or existing.summary
            a.body_snippet = (a.body_snippet or "").strip() or (getattr(existing, "body_snippet", "") or "")
            a.keywords = a.keywords or existing.keywords
            a.category = a.category or existing.category
            if use_llm_event_identifier:
                a.event_identifier = getattr(existing, "event_identifier", None) or a.event_identifier
            to_update.append(a)
            continue

        a.id = str(uuid.uuid4())[:8]
        matched_gid: Optional[str] = None
        matched_standalone_id: Optional[str] = None
        matched_from_batch: Optional[Article] = None
        ref_a = _ref(a)

        for eid in recent_titles:
            etitle, _ = recent_titles[eid]
            ref_e = _ref_recent(eid)
            sim = _title_similarity(ref_a, ref_e)
            if sim >= threshold:
                g = repo.get_group_for_article(eid)
                if g:
                    matched_gid = g.id
                else:
                    matched_standalone_id = eid
                break
            if use_gray and gray_min <= sim < gray_max:
                other = repo.get_article(eid)
                if other and _same_event(a, other):
                    g = repo.get_group_for_article(eid)
                    if g:
                        matched_gid = g.id
                    else:
                        matched_standalone_id = eid
                    break

        if not matched_gid and not matched_standalone_id:
            for bid, btitle, b_ident, b_art in current_batch:
                ref_b = (b_ident or "").strip() or btitle
                sim = _title_similarity(ref_a, ref_b)
                if sim >= threshold:
                    matched_from_batch = b_art
                    break
                if use_gray and gray_min <= sim < gray_max and _same_event(a, b_art):
                    matched_from_batch = b_art
                    break

        if matched_gid:
            g = repo.get_group(matched_gid)
            if g:
                g.source_article_ids = list(g.source_article_ids) + [a.id]
                g.source_urls = list(g.source_urls) + [{"url": a.url, "source": a.source, "title": a.title}]
                g.updated_at = datetime.utcnow()
                repo.update_group(g)
                groups_updated.append(g)
            a.duplicate_group_id = matched_gid
            to_insert.append(a)
            current_batch.append((a.id, a.title or "", getattr(a, "event_identifier", None), a))
        elif matched_standalone_id:
            other = repo.get_article(matched_standalone_id)
            if other and not other.duplicate_group_id:
                _short = (other.title or "").strip()
                short_title = (_short[:80] + "…") if len(_short) > 80 else _short or "통합 뉴스"
                g = DuplicateGroup(
                    id=str(uuid.uuid4())[:8],
                    canonical_article_id=other.id,
                    merged_summary=other.summary or other.title or "요약 없음",
                    merged_title=short_title,
                    merged_content=None,
                    source_article_ids=[other.id, a.id],
                    source_urls=[
                        {"url": other.url, "source": other.source, "title": other.title},
                        {"url": a.url, "source": a.source, "title": a.title},
                    ],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    merge_status="auto",
                    published_at=other.published_at,
                    category=other.category,
                    keywords=other.keywords or [],
                    importance=getattr(other, "importance", None) or 75.0,
                )
                repo.insert_group(g)
                groups_updated.append(g)
                other.duplicate_group_id = g.id
                if other.importance is None:
                    other.importance = 75.0
                repo.update_article(other)
                a.duplicate_group_id = g.id
            to_insert.append(a)
            current_batch.append((a.id, a.title or "", getattr(a, "event_identifier", None), a))
        elif matched_from_batch:
            other = matched_from_batch
            gid = getattr(other, "duplicate_group_id", None)
            if gid:
                g = repo.get_group(gid)
                if g:
                    g.source_article_ids = list(g.source_article_ids) + [a.id]
                    g.source_urls = list(g.source_urls) + [{"url": a.url, "source": a.source, "title": a.title}]
                    g.updated_at = datetime.utcnow()
                    repo.update_group(g)
                    groups_updated.append(g)
                a.duplicate_group_id = gid
            else:
                _short = (other.title or "").strip()
                short_title = (_short[:80] + "…") if len(_short) > 80 else _short or "통합 뉴스"
                g = DuplicateGroup(
                    id=str(uuid.uuid4())[:8],
                    canonical_article_id=other.id,
                    merged_summary=other.summary or other.title or "요약 없음",
                    merged_title=short_title,
                    merged_content=None,
                    source_article_ids=[other.id, a.id],
                    source_urls=[
                        {"url": other.url, "source": other.source, "title": other.title},
                        {"url": a.url, "source": a.source, "title": a.title},
                    ],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    merge_status="auto",
                    published_at=other.published_at,
                    category=other.category,
                    keywords=other.keywords or [],
                    importance=getattr(other, "importance", None) or 75.0,
                )
                repo.insert_group(g)
                groups_updated.append(g)
                other.duplicate_group_id = g.id
                a.duplicate_group_id = g.id
            to_insert.append(a)
            current_batch.append((a.id, a.title or "", getattr(a, "event_identifier", None), a))
        else:
            to_insert.append(a)
            current_batch.append((a.id, a.title or "", getattr(a, "event_identifier", None), a))

    return to_insert, to_update, groups_updated
