"""API 라우트: 인증, 피드, 검색, 기사/그룹 상세."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .auth import (
    create_session,
    destroy_session,
    get_session_id,
    require_auth,
    verify_password,
)

api_router = APIRouter()


def _utc_iso(iso_str):
    """저장된 ISO 시각을 UTC로 통일해 반환. 타임존 없으면 UTC로 간주하고 'Z' 부여. +00:00 → Z. 프론트에서 KST로 표시."""
    if not iso_str:
        return iso_str
    s = str(iso_str).strip()
    if len(s) >= 19 and s[10] == "T":
        if s.endswith("+00:00") or s.endswith("+0000"):
            return s[:-6].rstrip("Z") + "Z"
        if "Z" not in s and (len(s) <= 19 or s[-6] not in "-+"):
            return s.rstrip("Z") + "Z"
    return s


# 저장소 (앱에서 주입하거나 여기서 로드)
def get_repo():
    from src.config import load_config
    config = load_config()
    from src.storage.repository import Repository
    return Repository(config["storage"]["path"])


@api_router.post("/auth/login")
async def login(request: Request, response: Response):
    body = await request.json()
    password = (body.get("password") or "").strip()
    if not verify_password(password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    sid = create_session()
    response.set_cookie(key="news_agent_sid", value=sid, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return {"ok": True}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response, _: str = Depends(require_auth)):
    sid = get_session_id(request)
    if sid:
        destroy_session(sid)
    response.delete_cookie("news_agent_sid")
    return {"ok": True}


def _serialize_feed_item(item, item_type: str):
    if item_type == "group":
        ms = item.get("merged_summary") or ""
        if not ms.strip():
            ms = (item.get("merged_content") or "")[:500].strip() or "요약 없음"
        mt = item.get("merged_title") or ""
        if not mt.strip():
            mt = ms[:80] + ("…" if len(ms) > 80 else "") or "통합 뉴스"
        return {
            "type": "group",
            "id": item["id"],
            "merged_title": mt,
            "merged_summary": ms,
            "published_at": _utc_iso(item.get("published_at")),
            "category": item.get("category") or "",
            "keywords": item.get("keywords") or [],
            "source_urls": item.get("source_urls") or [],
            "importance": item.get("importance"),
        }
    return {
        "type": "article",
        "id": item["id"],
        "title": item.get("title") or "",
        "headline": item.get("headline") or "",
        "summary": item.get("summary") or "",
        "url": item.get("url") or "",
        "source": item.get("source") or "",
        "published_at": _utc_iso(item.get("published_at")),
        "category": item.get("category") or "",
        "keywords": item.get("keywords") or [],
        "importance": item.get("importance"),
    }


@api_router.get("/feed/dates")
async def feed_dates(
    _: str = Depends(require_auth),
    category: str = None,
    keyword: str = None,
    source: str = None,
):
    """날짜별 페이지네이션용: 뉴스가 있는 날짜 목록 (최신순)."""
    repo = get_repo()
    dates = repo.get_feed_dates(limit=60, category=category, keyword=keyword, source=source)
    return {"dates": dates, "total": len(dates)}


@api_router.get("/feed")
async def feed(
    request: Request,
    _: str = Depends(require_auth),
    category: str = None,
    keyword: str = None,
    source: str = None,
    date: str = None,
):
    """피드: date 있으면 해당 일자만(중요도 순), 없으면 가장 최근 일자. 날짜별 페이지네이션."""
    repo = get_repo()
    fetch_limit = 2000
    date_ymd = date.strip() if date and date.strip() else None
    if not date_ymd:
        dates = repo.get_feed_dates(limit=1, category=category, keyword=keyword, source=source)
        date_ymd = dates[0] if dates else None
    if not date_ymd:
        return {"items": [], "total": 0, "date": None, "date_label": None}

    groups = repo.list_groups_for_feed(
        limit=fetch_limit, offset=0, category=category, keyword=keyword, source=source, date_ymd=date_ymd
    )
    articles = repo.list_articles_for_feed(
        limit=fetch_limit, offset=0, category=category, keyword=keyword, source=source, date_ymd=date_ymd
    )

    items = []
    for g in groups:
        d = g.to_dict()
        d["published_at"] = d.get("published_at") or ""
        items.append(_serialize_feed_item(d, "group"))
    for a in articles:
        d = a.to_dict()
        d["published_at"] = d.get("published_at") or ""
        items.append(_serialize_feed_item(d, "article"))

    # 해당 일자 내에서는 중요도 순 (이미 DB에서 importance DESC)
    def sort_key(x):
        imp = x.get("importance")
        imp = float(imp) if imp is not None else 0
        pt = x.get("published_at") or ""
        try:
            ts = (pt and pt.replace("Z", "+00:00")) or "1970-01-01"
            from datetime import datetime
            t = datetime.fromisoformat(ts)
            tms = t.timestamp()
        except Exception:
            tms = 0
        return (-imp, -tms)

    items.sort(key=sort_key)
    # 날짜 라벨 (예: 3월 14일)
    try:
        from datetime import datetime
        dt = datetime.strptime(date_ymd, "%Y-%m-%d")
        date_label = f"{dt.month}월 {dt.day}일"
    except Exception:
        date_label = date_ymd
    return {"items": items, "total": len(items), "date": date_ymd, "date_label": date_label}


@api_router.get("/feed/filters")
async def feed_filters(_: str = Depends(require_auth)):
    repo = get_repo()
    return repo.get_feed_filter_options()


@api_router.get("/search")
async def search(
    request: Request,
    q: str = "",
    _: str = Depends(require_auth),
    limit: int = 50,
    offset: int = 0,
):
    if not q or not q.strip():
        return {"items": [], "total": 0}
    repo = get_repo()
    import sqlite3
    conn = sqlite3.connect(repo.db_path)
    conn.row_factory = lambda cursor, row: {cursor.description[i][0]: row[i] for i in range(len(row))}

    pattern = f"%{q.strip()}%"
    # 1) 기사: 제목/요약/키워드 LIKE
    cur = conn.execute("""
        SELECT id, url, url_hash, title, summary, source, published_at, keywords, category, duplicate_group_id, importance
        FROM articles WHERE title LIKE ? OR summary LIKE ? OR keywords LIKE ?
        ORDER BY published_at DESC
    """, (pattern, pattern, pattern))
    article_rows = cur.fetchall()
    # 2) 그룹(카드): 통합 제목/통합 요약 LIKE
    cur = conn.execute("""
        SELECT id FROM duplicate_groups
        WHERE merged_title LIKE ? OR merged_summary LIKE ? OR merged_content LIKE ?
    """, (pattern, pattern, pattern))
    group_ids_from_content = {row["id"] for row in cur.fetchall()}
    conn.close()

    seen_groups = set()
    items = []
    for r in article_rows:
        gid = r.get("duplicate_group_id")
        if gid and gid not in seen_groups:
            seen_groups.add(gid)
            g = repo.get_group(gid)
            if g:
                d = g.to_dict()
                d["published_at"] = _utc_iso(d.get("published_at"))
                items.append(_serialize_feed_item(d, "group"))
        elif not gid:
            kw = r.get("keywords")
            if isinstance(kw, str):
                try:
                    import json
                    kw = json.loads(kw) if kw else []
                except Exception:
                    kw = []
            items.append(_serialize_feed_item({
                "id": r["id"], "title": r["title"], "summary": r["summary"], "url": r["url"],
                "source": r["source"], "published_at": _utc_iso(r.get("published_at")), "keywords": kw or [],
                "category": r["category"], "importance": r.get("importance"),
            }, "article"))

    for gid in group_ids_from_content:
        if gid in seen_groups:
            continue
        seen_groups.add(gid)
        g = repo.get_group(gid)
        if g:
            d = g.to_dict()
            d["published_at"] = _utc_iso(d.get("published_at"))
            items.append(_serialize_feed_item(d, "group"))

    items = sorted(items, key=lambda x: (x.get("published_at") or ""), reverse=True)[:limit]
    return {"items": items, "total": len(items)}


@api_router.get("/highlights")
async def highlights(
    _: str = Depends(require_auth),
    days: int = 7,
    top_k: int = 12,
    refresh: int = 0,
):
    """
    주요뉴스(최근 N일) LLM 선별 결과 반환.
    refresh=1이면 캐시 무시하고 재생성.
    """
    repo = get_repo()
    days = max(1, min(int(days or 7), 30))
    top_k = max(3, min(int(top_k or 12), 30))
    cache_key = f"highlights:{days}d:top{top_k}"
    if not refresh:
        cached = repo.get_digest(cache_key)
        if cached and cached.get("payload"):
            return {"cached": True, **cached["payload"]}

    from src.config import load_config
    config = load_config()
    from src.pipeline.run_pipeline import _gemini_client
    client = _gemini_client(config)
    candidates = repo.list_major_candidates_last_days(days=days, limit=160)
    # 후보가 너무 적으면 그대로 importance 상위로 반환
    if not client or len(candidates) < 3:
        items = sorted(candidates, key=lambda x: float(x.get("importance") or 0), reverse=True)[:top_k]
        payload = {"days": days, "top_k": top_k, "editorial_summary": "", "items": items}
        repo.upsert_digest(cache_key, payload)
        return {"cached": False, **payload}

    from src.pipeline.gemini_processor import select_major_news
    gconf = config.get("google_ai") or {}
    min_interval = float(gconf.get("min_interval_seconds") or 1.0)
    sel = select_major_news(client, candidates, days=days, top_k=top_k, min_interval=min_interval)
    if not sel or not sel.get("selected"):
        items = sorted(candidates, key=lambda x: float(x.get("importance") or 0), reverse=True)[:top_k]
        payload = {"days": days, "top_k": top_k, "editorial_summary": "", "items": items}
        repo.upsert_digest(cache_key, payload)
        return {"cached": False, **payload}

    # selected -> 실제 아이템 매핑 + reason 붙이기
    idx = {(c["type"], c["id"]): c for c in candidates}
    out_items = []
    for s in sel["selected"]:
        key = (s.get("type"), s.get("id"))
        c = idx.get(key)
        if not c:
            continue
        item = dict(c)
        item["reason"] = s.get("reason") or ""
        out_items.append(item)
        if len(out_items) >= top_k:
            break

    payload = {
        "days": days,
        "top_k": top_k,
        "editorial_summary": sel.get("editorial_summary") or "",
        "items": out_items,
    }
    repo.upsert_digest(cache_key, payload)
    return {"cached": False, **payload}


@api_router.get("/articles/{id}")
async def get_article(id: str, _: str = Depends(require_auth)):
    repo = get_repo()
    a = repo.get_article(id)
    if not a:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    d = a.to_dict()
    if d.get("published_at"):
        d["published_at"] = _utc_iso(d["published_at"])
    group = None
    if a.duplicate_group_id:
        g = repo.get_group(a.duplicate_group_id)
        if g:
            group = g.to_dict()
            if not (group.get("merged_content") or "").strip() and (g.source_article_ids or []):
                fallback_content, fallback_summary = _fallback_group_content(repo, g)
                if fallback_content:
                    group["merged_content"] = fallback_content
                if not (group.get("merged_summary") or "").strip() and fallback_summary:
                    group["merged_summary"] = fallback_summary
            if not (group.get("merged_summary") or "").strip():
                group["merged_summary"] = (group.get("merged_content") or "")[:500].strip() or "요약 없음"
            source_articles = []
            for aid in g.source_article_ids:
                sa = repo.get_article(aid)
                if sa:
                    source_articles.append({"id": sa.id, "title": sa.title, "source": sa.source, "url": sa.url})
            group["source_articles"] = source_articles
    chains = repo.get_chains_for_article(id)
    return {"article": d, "group": group, "related_history": {"chains": chains}}


def _fallback_group_content(repo, g) -> tuple:
    """그룹 merged_content/merged_summary가 비어 있을 때 소속 기사 본문으로 채우기."""
    parts = []
    for aid in (g.source_article_ids or []):
        a = repo.get_article(aid)
        if not a:
            continue
        body = (getattr(a, "body_snippet", "") or "").strip()
        summary = (getattr(a, "summary", "") or "").strip()
        text = body or summary or (a.title or "")
        if text:
            parts.append(text)
    if not parts:
        return "", ""
    merged = "\n\n".join(parts)
    summary = (merged[:500] + "…") if len(merged) > 500 else merged
    return merged, summary


@api_router.get("/groups/{id}")
async def get_group(id: str, _: str = Depends(require_auth)):
    repo = get_repo()
    g = repo.get_group(id)
    if not g:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    d = g.to_dict()
    if d.get("published_at"):
        d["published_at"] = _utc_iso(d["published_at"])
    if not (d.get("merged_content") or "").strip() and (g.source_article_ids or []):
        fallback_content, fallback_summary = _fallback_group_content(repo, g)
        if fallback_content:
            d["merged_content"] = fallback_content
        if not (d.get("merged_summary") or "").strip() and fallback_summary:
            d["merged_summary"] = fallback_summary
    if not (d.get("merged_summary") or "").strip():
        d["merged_summary"] = (d.get("merged_content") or "")[:500].strip() or "요약 없음"
    if not (d.get("merged_title") or "").strip():
        d["merged_title"] = (d.get("merged_summary") or "")[:80] + ("…" if len(d.get("merged_summary") or "") > 80 else "") or "통합 뉴스"
    source_articles = []
    for aid in g.source_article_ids:
        a = repo.get_article(aid)
        if a:
            source_articles.append({"id": a.id, "title": a.title, "source": a.source, "url": a.url})
    d["source_articles"] = source_articles
    canonical_id = g.canonical_article_id
    chains = repo.get_chains_for_article(canonical_id) if canonical_id else []
    d["related_history"] = {"chains": chains}
    return d
