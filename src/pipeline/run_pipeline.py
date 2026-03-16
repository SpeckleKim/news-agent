"""파이프라인 오케스트레이션: 수집 → 정규화 → 중복 → Gemini → 저장."""
import logging
from datetime import datetime
from typing import Optional

from src.collectors import run_all_collectors
from src.config import get_api_key, load_config
from src.pipeline.dedup import run_dedup
from src.pipeline.gemini_processor import (
    _ensure_paragraph_breaks,
    are_same_event,
    assess_importance,
    classify_and_keywords,
    extract_event_identifier,
    headline_from_summary,
    merge_content,
    summarize,
)
from src.models import DuplicateGroup
from src.pipeline.normalize import raw_to_article
from src.pipeline.related_chains import build_related_chains
from src.storage.repository import Repository

logger = logging.getLogger(__name__)


def _strip_trailing_ellipsis(text: str) -> str:
    """통합한 내용 끝의 말줄임(... / …)만 제거. 마침표(.)는 유지."""
    if not text:
        return text
    s = text.rstrip()
    while s.endswith("...") or s.endswith("…"):
        if s.endswith("..."):
            s = s[:-3].rstrip()
        else:
            s = s[:-1].rstrip()
    return s


def _first_sentence(text: str, max_len: int = 120) -> str:
    """통합 요약에서 대표 제목용 첫 문장 추출 (마침표·줄바꿈 기준, 최대 max_len자)."""
    if not (text and text.strip()):
        return ""
    s = text.strip()
    for sep in (". ", ".\n", "\n", "。"):
        idx = s.find(sep)
        if idx != -1:
            s = s[: idx + 1].strip()
            break
    return (s[:max_len] + "…") if len(s) > max_len else s


def _short_title(title: str, max_len: int = 80) -> str:
    """카드 제목용으로 긴 뉴스 제목을 자름. 뉴스 제목 그대로 쓰지 않고 짧게."""
    if not (title and title.strip()):
        return "통합 뉴스"
    s = (title or "").strip()
    return (s[:max_len] + "…") if len(s) > max_len else s


def _gemini_client(config: dict):
    g = config.get("google_ai") or {}
    key = get_api_key(config, g.get("api_key_env"))
    model = g.get("model") or "gemini-2.5-flash-lite"
    if not key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=key)
        return (client, model)
    except Exception as e:
        logger.warning("Gemini client init failed: %s", e)
        return None


def run_pipeline(config: dict, max_raw: Optional[int] = None) -> None:
    repo = Repository(config["storage"]["path"])
    client = _gemini_client(config)
    if not client:
        logger.warning(
            "LLM 비활성: GOOGLE_AI_API_KEY(또는 config google_ai.api_key_env)가 없거나 초기화 실패. "
            "요약·카드제목·분류·중요도는 fallback만 사용됩니다 (제목 일부, 첫문장 등)."
        )
    g = config.get("google_ai") or {}
    min_interval = float(g.get("min_interval_seconds") or 1.0)
    max_articles = int(g.get("max_articles_per_run") or 50)
    merge_union_style = bool(g.get("merge_content_union_style", False))
    collected_at = datetime.utcnow()

    raw_list = run_all_collectors(config, max_items=max_raw)
    if max_raw is not None and max_raw > 0:
        raw_list = raw_list[: max_raw]
        logger.info("Limited to first %d raw items (test mode)", len(raw_list))
    if raw_list:
        logger.info("Collected raw: %d items from sources", len(raw_list))
        articles = [raw_to_article(r, collected_at) for r in raw_list]
        d_config = config.get("dedup") or {}
        use_llm_event = bool(d_config.get("use_llm_event_identifier", False))
        if use_llm_event and client:
            for a in articles:
                if not repo.get_by_url_hash(a.url_hash):
                    ident = extract_event_identifier(
                        client, a.title or "", (a.summary or "") or (getattr(a, "body_snippet", "") or ""), min_interval
                    )
                    if ident:
                        a.event_identifier = ident
        gray_min = float(d_config.get("llm_same_event_gray_zone_min") or 0)
        gray_max = float(d_config.get("llm_same_event_gray_zone_max") or 0)
        to_insert, to_update, groups_updated = run_dedup(
            repo, articles,
            threshold=float(d_config.get("title_similarity_threshold") or 0.88),
            use_llm_event_identifier=use_llm_event,
            llm_same_event_client=client if use_llm_event else None,
            llm_min_interval=min_interval,
            gray_min=gray_min,
            gray_max=gray_max,
        )

        for a in to_update:
            existing = repo.get_article(a.id)
            if a.importance is None and existing:
                a.importance = getattr(existing, "importance", None) or 75.0
            repo.update_article(a)

        # RPM/TPM 한계: Gemini 호출은 최대 max_articles 건만 (요약·분류)
        to_process = to_insert[:max_articles]
        for a in to_process:
            if not a.summary and a.body_snippet:
                a.summary = summarize(client, a.body_snippet, min_interval=min_interval) or a.title[:200]
            if not a.category and (a.title or a.body_snippet):
                cat_kw = classify_and_keywords(client, a.title, a.body_snippet or "", min_interval=min_interval)
                a.category = cat_kw.get("category") or ""
                a.keywords = cat_kw.get("keywords") or []
            if a.importance is None and (a.summary or a.title):
                a.importance = assess_importance(
                    client, a.title, a.summary or a.body_snippet or "", a.category or "", min_interval=min_interval
                )
            if a.importance is None:
                a.importance = 70.0 + (hash(a.id) % 21)
            if (a.summary or a.title) and not getattr(a, "headline", None):
                a.headline = headline_from_summary(client, a.summary or a.title, min_interval=min_interval) or _first_sentence(a.summary or a.title) or _short_title(a.title)
            repo.insert_article(a)
        for a in to_insert[max_articles:]:
            if a.importance is None:
                a.importance = 70.0 + (hash(a.id) % 21)
            if not getattr(a, "headline", None) and (a.summary or a.title):
                a.headline = _first_sentence(a.summary or a.title) or _short_title(a.title)
            repo.insert_article(a)

        for g in groups_updated:
            if g.merge_status == "edited":
                continue
            arts = [repo.get_article(aid) for aid in g.source_article_ids]
            arts = [x for x in arts if x]
            if arts:
                # 1.1 통합한 내용: 뉴스 하나는 무조건 넣음 (1건 → 해당 기사 원문, 여러 건 → 합집합)
                if len(arts) == 1:
                    single = arts[0]
                    body = (getattr(single, "body_snippet", "") or "").strip()
                    summary = (getattr(single, "summary", "") or "").strip()
                    merged_content = body or summary or (single.title or "")
                else:
                    merged_content = merge_content(
                        client, arts, min_interval=min_interval, merge_union_style=merge_union_style
                    )
                if not merged_content and arts:
                    first = arts[0]
                    merged_content = (getattr(first, "body_snippet", "") or getattr(first, "summary", "") or first.title or "내용 없음")
                merged_content = _ensure_paragraph_breaks((merged_content or "").strip())
                g.merged_content = _strip_trailing_ellipsis(merged_content) if merged_content else (g.merged_content or "")

                # 1.2 통합 요약: 통합한 내용을 기반으로 요약 (비지 않도록 fallback)
                if g.merged_content:
                    merged = summarize(client, g.merged_content, max_chars=500, min_interval=min_interval)
                    g.merged_summary = (merged or _first_sentence(g.merged_content) or (arts[0].summary if arts else "") or (arts[0].title if arts else "") or "요약 없음").strip() or "요약 없음"
                else:
                    g.merged_summary = (g.merged_summary or (arts[0].summary if arts else "") or (arts[0].title if arts else "") or "요약 없음").strip() or "요약 없음"

                # 1.3 카드 제목: 통합 요약 기반 한 줄. 뉴스 제목 그대로 쓰지 않고 짧은 형식만
                g.merged_title = (headline_from_summary(client, g.merged_summary, min_interval=min_interval) or _first_sentence(g.merged_summary) or _short_title(arts[0].title if arts else "") or "통합 뉴스").strip() or "통합 뉴스"
                if g.importance is None and (g.merged_summary or g.merged_content):
                    g.importance = assess_importance(
                        client,
                        g.merged_title or (arts[0].title if arts else ""),
                        g.merged_summary or (g.merged_content or "")[:2000],
                        g.category or (arts[0].category if arts else ""),
                        min_interval=min_interval,
                    )
                if g.importance is None and arts:
                    g.importance = getattr(arts[0], "importance", None) or 75.0
                if g.importance is None:
                    g.importance = 75.0
                g.updated_at = datetime.utcnow()
                repo.update_group(g)

        logger.info(
            "Pipeline done: collected=%d → inserted=%s updated=%s groups=%s (same URL = 갱신만, 새 URL = 신규 삽입)",
            len(raw_list), len(to_insert), len(to_update), len(groups_updated),
        )
    else:
        logger.info("No articles collected this run")

    # 수집 유무와 관계없이 기존 DB 기준으로 연관 체인 재구성
    build_related_chains(repo)


def _union_find_parent(parent: list, i: int) -> int:
    if parent[i] != i:
        parent[i] = _union_find_parent(parent, parent[i])
    return parent[i]


def regroup_recent_articles(repo: Repository, config: dict, limit: int = 33) -> None:
    """
    최근 수집한 N건을 그룹에서 빼고, 같은 내용인지 사람처럼 판단해 다시 묶은 뒤
    통합한 내용 = 합집합을 LLM으로 통합(merge_content), 통합 요약·카드 제목 생성 후 저장.
    """
    from src.pipeline.dedup import _title_similarity

    recent = repo.get_recent_articles(limit=limit)
    if not recent:
        logger.info("regroup_recent: no recent articles")
        return
    ids = [a.id for a in recent]
    repo.remove_articles_from_groups(ids)
    d_config = config.get("dedup") or {}
    threshold = float(d_config.get("title_similarity_threshold") or 0.75)
    use_llm_event = bool(d_config.get("use_llm_event_identifier", False))
    gray_min = float(d_config.get("llm_same_event_gray_zone_min") or 0)
    gray_max = float(d_config.get("llm_same_event_gray_zone_max") or 0)
    use_gray_zone = use_llm_event and gray_min < gray_max and gray_max > 0

    n = len(recent)
    parent = list(range(n))

    if use_llm_event:
        client = _gemini_client(config)
        g_config = config.get("google_ai") or {}
        min_interval = float(g_config.get("min_interval_seconds") or 1.0)
        identifiers = []
        for a in recent:
            # 수집 시 이미 붙은 식별자가 있으면 재사용(재그룹 시 LLM 비일관성으로 같은 사건이 묶이지 않는 문제 방지)
            existing = (getattr(a, "event_identifier", None) or "").strip()
            if existing:
                ident = existing
            else:
                ident = extract_event_identifier(
                    client, a.title or "", (a.summary or "") or (getattr(a, "body_snippet", "") or ""), min_interval
                )
            identifiers.append(ident or (a.title or "")[:100])
        for i in range(n):
            for j in range(i + 1, n):
                ti, tj = recent[i].title or "", recent[j].title or ""
                idi, idj = identifiers[i], identifiers[j]
                sim = max(
                    _title_similarity(idi, idj),
                    _title_similarity(ti, idj),
                    _title_similarity(idi, tj),
                    _title_similarity(ti, tj),
                )
                if sim >= threshold:
                    pi, pj = _union_find_parent(parent, i), _union_find_parent(parent, j)
                    if pi != pj:
                        parent[pi] = pj
                elif use_gray_zone and gray_min <= sim < gray_max and client:
                    if are_same_event(
                        client,
                        recent[i].title or "",
                        (recent[i].summary or "") or (getattr(recent[i], "body_snippet", "") or ""),
                        recent[j].title or "",
                        (recent[j].summary or "") or (getattr(recent[j], "body_snippet", "") or ""),
                        min_interval,
                    ):
                        pi, pj = _union_find_parent(parent, i), _union_find_parent(parent, j)
                        if pi != pj:
                            parent[pi] = pj
    else:
        for i in range(n):
            for j in range(i + 1, n):
                if _title_similarity(recent[i].title or "", recent[j].title or "") >= threshold:
                    pi, pj = _union_find_parent(parent, i), _union_find_parent(parent, j)
                    if pi != pj:
                        parent[pi] = pj

    components: dict = {}
    for i in range(n):
        root = _union_find_parent(parent, i)
        components.setdefault(root, []).append(i)
    client = _gemini_client(config)
    g_config = config.get("google_ai") or {}
    min_interval = float(g_config.get("min_interval_seconds") or 1.0)
    merge_union_style = bool(g_config.get("merge_content_union_style", False))
    groups_created = 0
    for root, indices in components.items():
        if len(indices) < 2:
            continue
        arts = [recent[i] for i in indices]
        first = arts[0]
        g = DuplicateGroup(
            id=str(__import__("uuid").uuid4())[:8],
            canonical_article_id=first.id,
            merged_summary=first.summary or first.title or "요약 없음",
            merged_title=_short_title(first.title or ""),
            merged_content=None,
            source_article_ids=[a.id for a in arts],
            source_urls=[{"url": a.url, "source": a.source, "title": a.title} for a in arts],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            merge_status="auto",
            published_at=first.published_at,
            category=first.category,
            keywords=first.keywords or [],
            importance=getattr(first, "importance", None) or 75.0,
        )
        repo.insert_group(g)
        groups_created += 1
        for a in arts:
            a.duplicate_group_id = g.id
            repo.update_article(a)
        arts_db = [repo.get_article(aid) for aid in g.source_article_ids]
        arts_db = [x for x in arts_db if x]
        if not arts_db:
            continue
        if len(arts_db) == 1:
            single = arts_db[0]
            body = (getattr(single, "body_snippet", "") or "").strip()
            summary = (getattr(single, "summary", "") or "").strip()
            merged_content = body or summary or (single.title or "")
        else:
            merged_content = merge_content(
                client, arts_db, min_interval=min_interval, merge_union_style=merge_union_style
            )
        if not merged_content and arts_db:
            first_art = arts_db[0]
            merged_content = (getattr(first_art, "body_snippet", "") or getattr(first_art, "summary", "") or first_art.title or "내용 없음")
        merged_content = _ensure_paragraph_breaks((merged_content or "").strip())
        g.merged_content = _strip_trailing_ellipsis(merged_content) if merged_content else (g.merged_content or "")
        g.merged_summary = (summarize(client, g.merged_content, max_chars=500, min_interval=min_interval) or _first_sentence(g.merged_content) or (arts_db[0].summary if arts_db else "") or (arts_db[0].title if arts_db else "") or "요약 없음").strip() or "요약 없음"
        g.merged_title = (headline_from_summary(client, g.merged_summary, min_interval=min_interval) or _first_sentence(g.merged_summary) or _short_title(arts_db[0].title if arts_db else "") or "통합 뉴스").strip() or "통합 뉴스"
        if g.importance is None and arts_db:
            g.importance = getattr(arts_db[0], "importance", None) or 75.0
        if g.importance is None:
            g.importance = 75.0
        g.updated_at = datetime.utcnow()
        repo.update_group(g)
    build_related_chains(repo)
    logger.info("regroup_recent: %d articles → %d groups created (통합내용=합집합 LLM 반영)", len(recent), groups_created)

