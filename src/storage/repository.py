"""SQLite 저장소: articles, duplicate_groups, related_chains CRUD."""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from src.models import Article, DuplicateGroup, RelatedChain


def _dict_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


class Repository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    url_hash TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT,
                    body_snippet TEXT,
                    source TEXT,
                    published_at TEXT,
                    collected_at TEXT,
                    keywords TEXT,
                    category TEXT,
                    duplicate_group_id TEXT,
                    version INTEGER DEFAULT 1,
                    importance REAL
                );
                CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles(url_hash);
                CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
                CREATE INDEX IF NOT EXISTS idx_articles_group ON articles(duplicate_group_id);

                CREATE TABLE IF NOT EXISTS duplicate_groups (
                    id TEXT PRIMARY KEY,
                    canonical_article_id TEXT NOT NULL,
                    merged_summary TEXT,
                    merged_title TEXT,
                    merged_content TEXT,
                    source_article_ids TEXT,
                    source_urls TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    merge_status TEXT,
                    published_at TEXT,
                    category TEXT,
                    keywords TEXT,
                    importance REAL
                );

                CREATE TABLE IF NOT EXISTS related_chains (
                    id TEXT PRIMARY KEY,
                    article_ids TEXT,
                    topic_label TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
            """)
        self._migrate_importance_column()
        self._migrate_headline_column()
        self._migrate_event_identifier_column()

    def _migrate_event_identifier_column(self):
        """기존 DB에 event_identifier 컬럼이 없으면 추가."""
        with self._conn() as c:
            try:
                c.execute("ALTER TABLE articles ADD COLUMN event_identifier TEXT")
            except sqlite3.OperationalError:
                pass

    def _migrate_importance_column(self):
        """기존 DB에 importance 컬럼이 없으면 추가."""
        with self._conn() as c:
            for table in ("articles", "duplicate_groups"):
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN importance REAL")
                except sqlite3.OperationalError:
                    pass  # 컬럼 이미 있음

    def _migrate_headline_column(self):
        """기존 DB에 headline 컬럼이 없으면 추가."""
        with self._conn() as c:
            try:
                c.execute("ALTER TABLE articles ADD COLUMN headline TEXT")
            except sqlite3.OperationalError:
                pass

    def insert_article(self, a: Article) -> None:
        with self._conn() as c:
            c.execute("""
                INSERT INTO articles (id, url, url_hash, title, summary, body_snippet, source,
                    published_at, collected_at, keywords, category, duplicate_group_id, version, importance, headline, event_identifier)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                a.id, a.url, a.url_hash, a.title, a.summary or "", a.body_snippet or "",
                a.source or "", a.published_at.isoformat() if a.published_at else None,
                a.collected_at.isoformat() if a.collected_at else None,
                json.dumps(a.keywords or []), a.category or "", a.duplicate_group_id,
                a.version, a.importance, getattr(a, "headline", None) or "",
                getattr(a, "event_identifier", None) or "",
            ))

    def update_article(self, a: Article) -> None:
        with self._conn() as c:
            c.execute("""
                UPDATE articles SET title=?, summary=?, body_snippet=?, keywords=?, category=?,
                    collected_at=?, version=?, importance=?, headline=?, event_identifier=?, duplicate_group_id=?
                WHERE id=?
            """, (
                a.title, a.summary or "", a.body_snippet or "",
                json.dumps(a.keywords or []), a.category or "",
                a.collected_at.isoformat() if a.collected_at else None,
                a.version, a.importance, getattr(a, "headline", None) or "",
                getattr(a, "event_identifier", None) or "", a.duplicate_group_id, a.id
            ))

    def get_by_url_hash(self, url_hash: str) -> Optional[Article]:
        with self._conn() as c:
            c.row_factory = _dict_factory
            row = c.execute("SELECT * FROM articles WHERE url_hash=?", (url_hash,)).fetchone()
        return _row_to_article(row) if row else None

    def get_article(self, id: str) -> Optional[Article]:
        with self._conn() as c:
            c.row_factory = _dict_factory
            row = c.execute("SELECT * FROM articles WHERE id=?", (id,)).fetchone()
        return _row_to_article(row) if row else None

    def get_recent_titles(self, days: int = 7) -> List[Tuple[str, str]]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT id, title FROM articles
                WHERE published_at >= datetime('now', ? || ' days')
                ORDER BY published_at DESC
            """, (f"-{days}",)).fetchall()
        return [(r[0], r[1]) for r in rows]

    def get_recent_titles_and_identifiers(self, days: int = 14) -> List[Tuple[str, str, Optional[str]]]:
        """최근 기사 (id, title, event_identifier). event_identifier는 없을 수 있음."""
        try:
            with self._conn() as c:
                rows = c.execute("""
                    SELECT id, title, event_identifier FROM articles
                    WHERE published_at >= datetime('now', ? || ' days')
                    ORDER BY published_at DESC
                """, (f"-{days}",)).fetchall()
            return [(r[0], r[1], r[2] if len(r) > 2 and r[2] else None) for r in rows]
        except sqlite3.OperationalError:
            return [(aid, title, None) for aid, title in self.get_recent_titles(days)]

    def get_recent_articles(self, limit: int = 33) -> List[Article]:
        """수집 시각 기준 최근 N건 (재그룹 등에 사용)."""
        with self._conn() as c:
            c.row_factory = _dict_factory
            rows = c.execute(
                "SELECT * FROM articles ORDER BY collected_at DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
        return [_row_to_article(r) for r in rows if r]

    def remove_articles_from_groups(self, article_ids: List[str]) -> None:
        """지정 기사들을 그룹에서 빼고 duplicate_group_id=null 로 만듦. 그룹이 비면 삭제."""
        if not article_ids:
            return
        ids_set = set(article_ids)
        with self._conn() as c:
            for aid in ids_set:
                c.execute("UPDATE articles SET duplicate_group_id = NULL WHERE id = ?", (aid,))
            c.row_factory = _dict_factory
            rows = c.execute("SELECT id, source_article_ids, source_urls FROM duplicate_groups").fetchall()
        for row in rows:
            gid = row["id"]
            aids = json.loads(row["source_article_ids"]) if isinstance(row["source_article_ids"], str) else (row["source_article_ids"] or [])
            urls = json.loads(row["source_urls"]) if isinstance(row["source_urls"], str) else (row["source_urls"] or [])
            new_aids = [x for x in aids if x not in ids_set]
            new_urls = [urls[i] for i in range(len(aids)) if aids[i] not in ids_set]
            if not new_aids:
                with self._conn() as conn:
                    conn.execute("DELETE FROM duplicate_groups WHERE id = ?", (gid,))
            else:
                with self._conn() as conn:
                    conn.execute(
                        "UPDATE duplicate_groups SET source_article_ids = ?, source_urls = ?, updated_at = ? WHERE id = ?",
                        (json.dumps(new_aids), json.dumps(new_urls), datetime.utcnow().isoformat(), gid),
                    )

    def list_articles_for_feed(self, limit: int = 100, offset: int = 0,
                               category: Optional[str] = None, keyword: Optional[str] = None,
                               source: Optional[str] = None,
                               date_ymd: Optional[str] = None) -> List[Article]:
        with self._conn() as c:
            c.row_factory = _dict_factory
            sql = "SELECT * FROM articles WHERE duplicate_group_id IS NULL"
            params = []
            if category:
                sql += " AND category=?"
                params.append(category)
            if keyword:
                sql += " AND keywords LIKE ?"
                params.append(f"%{keyword}%")
            if source:
                sql += " AND source=?"
                params.append(source)
            if date_ymd:
                sql += " AND date(published_at)=?"
                params.append(date_ymd)
            sql += " ORDER BY importance DESC, published_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = c.execute(sql, params).fetchall()
        return [_row_to_article(r) for r in rows if r]

    def get_feed_dates(self, limit: int = 60,
                       category: Optional[str] = None, keyword: Optional[str] = None,
                       source: Optional[str] = None) -> List[str]:
        """피드에 나타날 수 있는 날짜 목록 (최신순). 날짜별 페이지네이션용."""
        with self._conn() as c:
            dates = set()
            # 그룹
            sql = "SELECT DISTINCT date(published_at) FROM duplicate_groups WHERE published_at IS NOT NULL"
            params = []
            if category:
                sql += " AND category=?"
                params.append(category)
            if keyword:
                sql += " AND keywords LIKE ?"
                params.append(f"%{keyword}%")
            if source:
                sql += " AND source_urls LIKE ?"
                params.append(f"%{source}%")
            for row in c.execute(sql, params).fetchall():
                if row[0]:
                    dates.add(row[0])
            # 단독 기사
            sql = "SELECT DISTINCT date(published_at) FROM articles WHERE duplicate_group_id IS NULL AND published_at IS NOT NULL"
            params = []
            if category:
                sql += " AND category=?"
                params.append(category)
            if keyword:
                sql += " AND keywords LIKE ?"
                params.append(f"%{keyword}%")
            if source:
                sql += " AND source=?"
                params.append(source)
            for row in c.execute(sql, params).fetchall():
                if row[0]:
                    dates.add(row[0])
        return sorted(dates, reverse=True)[: max(1, limit)]

    def insert_group(self, g: DuplicateGroup) -> None:
        with self._conn() as c:
            c.execute("""
                INSERT INTO duplicate_groups (id, canonical_article_id, merged_summary, merged_title,
                    merged_content, source_article_ids, source_urls, created_at, updated_at,
                    merge_status, published_at, category, keywords, importance)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                g.id, g.canonical_article_id, g.merged_summary, g.merged_title or "",
                g.merged_content or "", json.dumps(g.source_article_ids), json.dumps(g.source_urls),
                g.created_at.isoformat() if g.created_at else None,
                g.updated_at.isoformat() if g.updated_at else None,
                g.merge_status, g.published_at.isoformat() if g.published_at else None,
                g.category or "", json.dumps(g.keywords or []), g.importance
            ))

    def update_group(self, g: DuplicateGroup) -> None:
        with self._conn() as c:
            c.execute("""
                UPDATE duplicate_groups SET merged_summary=?, merged_title=?, merged_content=?,
                    source_article_ids=?, source_urls=?, updated_at=?, merge_status=?,
                    published_at=?, category=?, keywords=?, importance=?, canonical_article_id=?
                WHERE id=?
            """, (
                g.merged_summary, g.merged_title or "", g.merged_content or "",
                json.dumps(g.source_article_ids), json.dumps(g.source_urls),
                g.updated_at.isoformat() if g.updated_at else None,
                g.merge_status, g.published_at.isoformat() if g.published_at else None,
                g.category or "", json.dumps(g.keywords or []), g.importance,
                g.canonical_article_id, g.id
            ))

    def get_group(self, id: str) -> Optional[DuplicateGroup]:
        with self._conn() as c:
            c.row_factory = _dict_factory
            row = c.execute("SELECT * FROM duplicate_groups WHERE id=?", (id,)).fetchone()
        return _row_to_group(row) if row else None

    def get_group_for_article(self, article_id: str) -> Optional[DuplicateGroup]:
        art = self.get_article(article_id)
        if not art or not art.duplicate_group_id:
            return None
        return self.get_group(art.duplicate_group_id)

    def list_groups_for_feed(self, limit: int = 100, offset: int = 0,
                            category: Optional[str] = None, keyword: Optional[str] = None,
                            source: Optional[str] = None,
                            date_ymd: Optional[str] = None) -> List[DuplicateGroup]:
        with self._conn() as c:
            c.row_factory = _dict_factory
            sql = "SELECT * FROM duplicate_groups WHERE 1=1"
            params = []
            if category:
                sql += " AND category=?"
                params.append(category)
            if keyword:
                sql += " AND keywords LIKE ?"
                params.append(f"%{keyword}%")
            if source:
                sql += " AND source_urls LIKE ?"
                params.append(f"%{source}%")
            if date_ymd:
                sql += " AND date(published_at)=?"
                params.append(date_ymd)
            sql += " ORDER BY importance DESC, published_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = c.execute(sql, params).fetchall()
        return [_row_to_group(r) for r in rows if r]

    def get_chains_for_article(self, article_id: str) -> List[dict]:
        """해당 기사가 속한 연관 체인 목록 + 각 체인 내 이전/현재/다음 노드 (제목, 날짜, type 포함)."""
        with self._conn() as c:
            c.row_factory = _dict_factory
            rows = c.execute(
                "SELECT * FROM related_chains WHERE article_ids LIKE ?",
                (f"%{article_id}%",)
            ).fetchall()
        result = []
        for row in rows:
            ids = json.loads(row["article_ids"] or "[]")
            if article_id not in ids:
                continue
            idx = ids.index(article_id)
            items = []
            for i, nid in enumerate(ids):
                pos = "prev" if i < idx else ("current" if i == idx else "next")
                art = self.get_article(nid)
                if art:
                    items.append({
                        "id": nid, "position": pos, "type": "article",
                        "title": getattr(art, "headline", None) or art.title,
                        "published_at": art.published_at.isoformat() if art.published_at else None,
                    })
                else:
                    g = self.get_group(nid)
                    if g:
                        items.append({
                            "id": nid, "position": pos, "type": "group",
                            "title": g.merged_title or "통합 뉴스", "published_at": g.published_at.isoformat() if g.published_at else None,
                        })
                    else:
                        items.append({"id": nid, "position": pos, "type": "article", "title": "(알 수 없음)", "published_at": None})
            result.append({
                "chain_id": row["id"],
                "topic_label": row["topic_label"] or "",
                "items": items,
            })
        return result

    def insert_chain(self, ch: RelatedChain) -> None:
        with self._conn() as c:
            c.execute("""
                INSERT INTO related_chains (id, article_ids, topic_label, created_at, updated_at)
                VALUES (?,?,?,?,?)
            """, (
                ch.id, json.dumps(ch.article_ids), ch.topic_label or "",
                ch.created_at.isoformat() if ch.created_at else None,
                ch.updated_at.isoformat() if ch.updated_at else None
            ))

    def update_chain(self, ch: RelatedChain) -> None:
        with self._conn() as c:
            c.execute("""
                UPDATE related_chains SET article_ids=?, topic_label=?, updated_at=? WHERE id=?
            """, (json.dumps(ch.article_ids), ch.topic_label or "",
                  ch.updated_at.isoformat() if ch.updated_at else None, ch.id))

    def delete_all_chains(self) -> None:
        """연관 체인 전체 삭제 (파이프라인에서 재구성 전에 호출)."""
        with self._conn() as c:
            c.execute("DELETE FROM related_chains")

    def delete_all_data(self) -> None:
        """테스트용: 기사·그룹·연관체인 전체 삭제."""
        with self._conn() as c:
            c.execute("DELETE FROM related_chains")
            c.execute("DELETE FROM duplicate_groups")
            c.execute("DELETE FROM articles")

    def get_feed_filter_options(self) -> dict:
        """피드 필터용 실제 데이터에서 추출한 카테고리/키워드/출처 목록."""
        with self._conn() as c:
            categories = [r[0] for r in c.execute(
                "SELECT DISTINCT category FROM articles WHERE category IS NOT NULL AND category != ''"
            ).fetchall()]
            categories += [r[0] for r in c.execute(
                "SELECT DISTINCT category FROM duplicate_groups WHERE category IS NOT NULL AND category != ''"
            ).fetchall()]
            categories = sorted(set(categories))

            sources = [r[0] for r in c.execute(
                "SELECT DISTINCT source FROM articles WHERE source IS NOT NULL AND source != ''"
            ).fetchall()]
            for row in c.execute("SELECT source_urls FROM duplicate_groups WHERE source_urls IS NOT NULL AND source_urls != ''").fetchall():
                try:
                    urls = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    if isinstance(urls, list):
                        for u in urls:
                            if isinstance(u, dict) and u.get("source"):
                                sources.append(u["source"])
                except Exception:
                    pass
            sources = sorted(set(sources))

            keywords = set()
            for row in c.execute("SELECT keywords FROM articles WHERE keywords IS NOT NULL AND keywords != '' AND keywords != '[]'").fetchall():
                try:
                    kw = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    if isinstance(kw, list):
                        keywords.update(str(k) for k in kw if k)
                except Exception:
                    pass
            for row in c.execute("SELECT keywords FROM duplicate_groups WHERE keywords IS NOT NULL AND keywords != '' AND keywords != '[]'").fetchall():
                try:
                    kw = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    if isinstance(kw, list):
                        keywords.update(str(k) for k in kw if k)
                except Exception:
                    pass
            keywords = sorted(keywords)

        return {"categories": categories, "keywords": keywords, "sources": sources}


def _row_to_article(row: dict) -> Article:
    return Article(
        id=row["id"],
        url=row["url"],
        url_hash=row["url_hash"],
        title=row["title"],
        summary=row["summary"] or "",
        body_snippet=row["body_snippet"] or "",
        source=row["source"] or "",
        published_at=_parse_iso(row.get("published_at")),
        collected_at=_parse_iso(row.get("collected_at")),
        keywords=json.loads(row["keywords"]) if isinstance(row.get("keywords"), str) else (row.get("keywords") or []),
        category=row["category"] or "",
        duplicate_group_id=row.get("duplicate_group_id"),
        version=int(row.get("version") or 1),
        importance=float(row["importance"]) if row.get("importance") is not None else None,
        headline=row.get("headline") or None,
        event_identifier=row.get("event_identifier") or None,
    )


def _row_to_group(row: dict) -> DuplicateGroup:
    return DuplicateGroup(
        id=row["id"],
        canonical_article_id=row["canonical_article_id"],
        merged_summary=row["merged_summary"] or "",
        merged_title=row.get("merged_title"),
        merged_content=row.get("merged_content"),
        source_article_ids=json.loads(row["source_article_ids"]) if isinstance(row.get("source_article_ids"), str) else (row.get("source_article_ids") or []),
        source_urls=json.loads(row["source_urls"]) if isinstance(row.get("source_urls"), str) else (row.get("source_urls") or []),
        created_at=_parse_iso(row.get("created_at")),
        updated_at=_parse_iso(row.get("updated_at")),
        merge_status=row.get("merge_status") or "auto",
        published_at=_parse_iso(row.get("published_at")),
        category=row.get("category"),
        keywords=json.loads(row["keywords"]) if isinstance(row.get("keywords"), str) else (row.get("keywords") or []),
        importance=float(row["importance"]) if row.get("importance") is not None else None,
    )
