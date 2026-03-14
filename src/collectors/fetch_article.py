"""링크로 기사 페이지에 접속해 본문만 추출. URL 열기·복원·파싱 전체에 타임아웃 적용."""
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

import requests
from readability import Document

# Google 뉴스 리다이렉트 URL → 실제 기사 URL 복원
def _resolve_google_news_url(url: str) -> str:
    if "news.google.com" not in (url or ""):
        return url or ""
    try:
        from googlenewsdecoder import gnewsdecoder
        out = gnewsdecoder(url, interval=1)
        if out and out.get("status") and out.get("decoded_url"):
            return out["decoded_url"]
    except Exception:
        pass
    return url

# 본문 추출 결과 HTML → 순수 텍스트 (lxml 사용)
try:
    from lxml import html as lxml_html
    def _html_to_text(html: str) -> str:
        root = lxml_html.fromstring(html)
        return (root.text_content() or "").strip()
except ImportError:
    def _html_to_text(html: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
# URL 열 때 사용하는 HTTP 타임아웃(초)
DEFAULT_TIMEOUT = 12
# URL 복원 + 요청 + 파싱 전체를 감싸는 타임아웃(초). 이 시간 넘기면 None 반환 → 호출측에서 body 기본값(RSS 요약) 사용
DEFAULT_TOTAL_TIMEOUT = 25
DEFAULT_MAX_CHARS = 100_000


def _fetch_article_body_impl(url: str, http_timeout: int, max_chars: Optional[int]) -> Optional[str]:
    """실제 본문 수집 로직. 타임아웃은 호출측에서 전체 실행 시간으로 걸어 둠."""
    if not url or not url.strip():
        return None
    fetch_url = _resolve_google_news_url(url.strip())
    resp = requests.get(
        fetch_url,
        timeout=http_timeout,
        headers={"User-Agent": USER_AGENT},
        allow_redirects=True,
    )
    resp.raise_for_status()
    raw = resp.content
    if not raw:
        return None
    html_str = (resp.text if hasattr(resp, "text") else raw.decode(resp.encoding or "utf-8", errors="replace"))
    if not html_str or len(html_str) < 100:
        return None
    doc = Document(html_str)
    summary_html = doc.summary()
    if not summary_html or len(summary_html) < 50:
        return None
    text = _html_to_text(summary_html)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 80:
        return None
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars]
    return text


def fetch_article_body(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_chars: Optional[int] = DEFAULT_MAX_CHARS,
    total_timeout: int = DEFAULT_TOTAL_TIMEOUT,
) -> Optional[str]:
    """
    기사 URL에 요청해 본문만 추출해 반환.
    - URL 복원(Google 뉴스 디코딩) + HTTP 요청 + 파싱 전체에 total_timeout 적용. 초과 시 None → 호출측에서 body 기본값(RSS 요약) 사용.
    - HTTP 요청에는 timeout(초) 적용.
    실패·타임아웃 시 None. 성공 시 평문 텍스트.
    """
    if not url or not url.strip():
        return None
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_fetch_article_body_impl, url.strip(), timeout, max_chars)
            return future.result(timeout=total_timeout)
    except (FuturesTimeoutError, Exception):
        return None
