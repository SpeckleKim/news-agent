"""데이터 모델: Article, DuplicateGroup, RelatedChain."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    id: str
    url: str
    url_hash: str
    title: str
    summary: str
    body_snippet: str
    source: str
    published_at: datetime
    collected_at: datetime
    keywords: list
    category: str
    duplicate_group_id: Optional[str]
    version: int
    importance: Optional[float] = None  # 0~100, UI 정렬용
    headline: Optional[str] = None  # 카드용 헤드라인 (~습니다 없이)
    event_identifier: Optional[str] = None  # LLM 추출 '사건 식별 문구' (같은 내용 판별용)

    def to_dict(self):
        return {
            "id": self.id,
            "url": self.url,
            "url_hash": self.url_hash,
            "title": self.title,
            "summary": self.summary,
            "body_snippet": self.body_snippet,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "keywords": self.keywords or [],
            "category": self.category or "",
            "duplicate_group_id": self.duplicate_group_id,
            "version": self.version,
            "importance": self.importance,
            "headline": self.headline or "",
        }


@dataclass
class DuplicateGroup:
    id: str
    canonical_article_id: str
    merged_summary: str
    merged_title: Optional[str]
    merged_content: Optional[str]  # 통합한 내용(요약 외)
    source_article_ids: list
    source_urls: list  # [{url, title?, source}]
    created_at: datetime
    updated_at: datetime
    merge_status: str  # auto | manual | edited
    published_at: Optional[datetime] = None
    category: Optional[str] = None
    keywords: list = field(default_factory=list)
    importance: Optional[float] = None

    def to_dict(self):
        return {
            "id": self.id,
            "merged_title": self.merged_title or "",
            "merged_summary": self.merged_summary,
            "merged_content": self.merged_content or "",
            "source_urls": self.source_urls,
            "source_article_ids": self.source_article_ids,
            "canonical_article_id": self.canonical_article_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "merge_status": self.merge_status,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "category": self.category or "",
            "keywords": self.keywords or [],
            "importance": self.importance,
        }


@dataclass
class RelatedChain:
    id: str
    article_ids: list  # 시간순 (group이면 대표 id 또는 group_id 구분)
    topic_label: Optional[str]
    created_at: datetime
    updated_at: datetime

    def to_dict(self):
        return {
            "id": self.id,
            "chain_id": self.id,
            "article_ids": self.article_ids,
            "topic_label": self.topic_label or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
