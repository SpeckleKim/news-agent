"""수집기 베이스 및 RawArticle."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RawArticle:
    url: str
    title: str
    body_snippet: str = ""
    source: str = ""
    published_at: Optional[datetime] = None


class BaseCollector(ABC):
    @abstractmethod
    def collect(self, keywords: list = None) -> list:
        """키워드(선택)를 받아 RawArticle 리스트 반환."""
        pass
