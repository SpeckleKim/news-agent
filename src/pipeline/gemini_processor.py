"""Gemini 연동: 요약, 분류, 병합 요약, 중요도 평가. RPM/TPM 한계 고려. 실패 시 재시도. API 호출/결과 로그 기록."""
import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# 마지막 호출 시각. 호출 간 min_interval_seconds 대기.
_last_call_time: float = 0

# 재시도 설정
DEFAULT_MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # 초

# API 호출 결과 로그 (분석용). 환경변수 GEMINI_API_LOG 경로 또는 data/gemini_api.log
def _api_log_path() -> str:
    p = os.environ.get("GEMINI_API_LOG") or "data/gemini_api.log"
    if not os.path.isabs(p):
        p = os.path.join(os.getcwd(), p)
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
    return p


def _write_api_log(label: str, request_len: int, status: str, response_len: Optional[int] = None, preview: Optional[str] = None, error: Optional[str] = None) -> None:
    """한 줄 기록: timestamp | label | request_len | status | response_len=... | preview=... | error=..."""
    try:
        from datetime import datetime
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        parts = [ts, label, str(request_len), status]
        if response_len is not None:
            parts.append(f"response_len={response_len}")
        if preview is not None:
            safe = (preview[:80] + "…") if len(preview) > 80 else preview
            safe = safe.replace("\t", " ").replace("\n", " ")
            parts.append(f"preview={safe}")
        if error is not None:
            safe = (str(error)[:200] + "…") if len(str(error)) > 200 else str(error)
            safe = safe.replace("\t", " ").replace("\n", " ")
            parts.append(f"error={safe}")
        line = " | ".join(parts) + "\n"
        with open(_api_log_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.debug("Could not write API log: %s", e)


def _throttle(min_interval: float) -> None:
    global _last_call_time
    elapsed = time.monotonic() - _last_call_time
    if elapsed < min_interval and _last_call_time > 0:
        time.sleep(min_interval - elapsed)
    _last_call_time = time.monotonic()


def _get_client(api_key: Optional[str], model: str = "gemini-2.5-flash-lite"):
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        return client, model
    except Exception as e:
        logger.warning("Gemini client init failed: %s", e)
        return None


def _call_gemini(
    client_info,
    contents: str,
    min_interval: float = 1.0,
    max_retries: int = DEFAULT_MAX_RETRIES,
    call_label: str = "gemini",
) -> Optional[str]:
    """Gemini 호출. 순차(throttle) + 실패 시 재시도. 매 호출/결과를 API 로그 파일에 기록(분석용)."""
    if not client_info:
        return None
    client, model = client_info
    request_len = len(contents or "")
    last_error = None
    for attempt in range(max_retries):
        _throttle(min_interval)
        try:
            response = client.models.generate_content(model=model, contents=contents)
            if response and response.text:
                out = response.text.strip()
                _write_api_log(call_label, request_len, "OK", response_len=len(out), preview=out[:120])
                return out
            last_error = ValueError("empty response")
        except Exception as e:
            last_error = e
            logger.warning("Gemini call failed (attempt %d/%d): %s", attempt + 1, max_retries, e)
        if attempt < max_retries - 1:
            delay = RETRY_BASE_DELAY * (attempt + 1)
            logger.info("Retrying in %.1fs...", delay)
            time.sleep(delay)
    if last_error:
        logger.warning("Gemini call gave up after %d attempts: %s", max_retries, last_error)
        _write_api_log(call_label, request_len, "FAIL", error=f"{type(last_error).__name__}: {last_error}")
    return None


def assess_importance(
    client_info,
    title: str,
    summary_or_content: str,
    category: str = "",
    min_interval: float = 1.0,
) -> Optional[float]:
    """시장·기술 영향 기준으로 중요도 0~100을 LLM이 판단."""
    if not client_info:
        return None
    text = (summary_or_content or "")[:2000]
    title = (title or "").strip() or "제목 없음"
    contents = f"""다음 뉴스의 중요도를 0~100 점으로만 평가하세요.

【평가 기준】
- 시장·기술·산업에 미치는 영향 크기
- 파급력(다수 기업·투자·규제에 영향)
- 혁신성·첫 사례 여부
- 정책·규제·거시경제 관련성

【점수 구간】
- 90~100: 시장/기술에 매우 큰 영향 (예: 핵심 규제·대형 M&A·플랫폼급 기술 발표)
- 70~89: 상당한 영향 (주요 기업 전략, 신기술 도입, 업계 트렌드)
- 50~69: 일부 영향 (특정 기업·제품, 참고 수준 이슈)
- 30~49: 제한적 영향 (소규모 발표, 지역/니치)
- 0~29: 참고 수준 (단순 소식, 영향 미미)

제목: {title}
요약/본문 일부: {text}
분류: {category or '(없음)'}

숫자만 한 줄로 답하세요 (예: 75). 다른 설명 없이 0~100 정수만."""

    out = _call_gemini(client_info, contents, min_interval, call_label="importance")
    if not out:
        return None
    try:
        m = re.search(r"\b(\d{1,3})\b", out.strip())
        if m:
            val = float(m.group(1))
            return min(100.0, max(0.0, val))
    except Exception:
        pass
    return None


def summarize(client_info, text: str, max_chars: int = 300, min_interval: float = 1.0) -> Optional[str]:
    if not client_info or not text:
        return None
    snippet = (text or "")[:8000]
    if not snippet.strip():
        return ""
    contents = f"다음 뉴스 본문을 3문장 이내로 요약해 주세요. 핵심 수치·날짜는 유지하세요.\n\n{snippet}"
    out = _call_gemini(client_info, contents, min_interval, call_label="summarize")
    return out[:max_chars] if out else None


def classify_and_keywords(client_info, title: str, body: str, min_interval: float = 1.0) -> dict:
    if not client_info:
        return {"category": "", "keywords": []}
    contents = f"""다음 뉴스를 분류하고 키워드 3~5개를 추출하세요. JSON만 한 줄로 답하세요.
예: {{"category":"AI","keywords":["ChatGPT","OpenAI"]}}
분류: AI / 증권 / 금융 / IB 중 하나.
제목: {title}
본문 일부: {(body or '')[:1500]}
"""
    out = _call_gemini(client_info, contents, min_interval, call_label="classify")
    if not out:
        return {"category": "", "keywords": []}
    try:
        import json
        if "{" in out and "}" in out:
            start = out.index("{")
            end = out.rindex("}") + 1
            obj = json.loads(out[start:end])
            return {
                "category": (obj.get("category") or "").strip()[:50],
                "keywords": [str(k).strip() for k in (obj.get("keywords") or [])[:5] if k],
            }
    except Exception as e:
        logger.warning("Gemini classify parse failed: %s", e)
    return {"category": "", "keywords": []}


def headline_from_summary(client_info, summary_or_text: str, min_interval: float = 1.0) -> Optional[str]:
    """요약문을 카드용 헤드라인 한 줄로 변환. 단어·구 중심, 조사 생략, 서술형(~습니다) 금지."""
    if not client_info or not (summary_or_text and summary_or_text.strip()):
        return None
    text = (summary_or_text or "")[:1500]
    contents = f"""아래 뉴스 요약을 **카드 제목용 헤드라인 한 줄**로 바꾸세요.

[필수 규칙]
- **서술형·문장형 금지**: '~습니다', '~했다', '~한다' 등 동사로 끝내지 말 것.
- **회의·정상회담**이면 반드시 "제N차 ○○ 회의. 주제 요약" 형식으로. 예: "제10차 한일 재무장관회의. 통화 가치 급락·외환시장 공조"
- 그 외는 단어·구 형식으로. 조사 생략, 신문 헤드라인처럼 간결하게.

[좋은 예]
- 한일 재무장관 회의 뉴스 → "제10차 한일 재무장관회의. 통화 가치 급격한 하락 논의"
- "크래프톤이 9% 급등하며 한화에어로와 피지컬 AI 동맹을 체결했습니다" → "크래프톤 9% 급등…한화에어로와 피지컬 AI 동맹"
- "금융위가 금융소비자보호법 개정에 착수했습니다" → "금융위, 금융소비자보호법 개정 착수"

[출력] 헤드라인 한 줄만, 따옴표 없이.

{text}
"""
    out = _call_gemini(client_info, contents, min_interval, call_label="headline")
    return (out.strip().strip('"\'')[:200]) if out else None


def select_major_news(
    client_info,
    candidates: list,
    days: int = 7,
    top_k: int = 12,
    min_interval: float = 1.0,
) -> Optional[dict]:
    """
    최근 N일 후보 중 '주요뉴스' top_k를 LLM으로 선별.
    반환: {"days": int, "top_k": int, "selected": [{"type","id","reason"}], "editorial_summary": str}
    """
    if not client_info or not candidates:
        return None
    days = max(1, int(days or 7))
    top_k = max(3, min(int(top_k or 12), 30))

    def _imp(x):
        try:
            return float(x.get("importance") or 0)
        except Exception:
            return 0.0

    # 후보는 중요도 상위 중심으로 최대 60개만 넣어 토큰/비용 제한
    cand = sorted(list(candidates), key=_imp, reverse=True)[:60]
    lines = []
    for i, c in enumerate(cand, 1):
        t = (c.get("title") or "").strip().replace("\n", " ")
        s = (c.get("summary") or "").strip().replace("\n", " ")
        pt = (c.get("published_at") or "").strip()
        imp = c.get("importance")
        lines.append(f"{i}. [{c.get('type')}:{c.get('id')}] ({pt}) imp={imp} | {t} :: {s[:180]}")
    catalog = "\n".join(lines)

    contents = f"""너는 뉴스 편집장이다. 아래 후보는 최근 {days}일 내 뉴스(그룹/단독)이다.
목표: 독자가 '이번 주 꼭 알아야 할' **주요뉴스 {top_k}개**만 고른다.

[선정 기준]
- 파급력/중요도(산업·시장·정책 영향)
- 기술·제품의 본질적 변화, 대형 투자/인수/규제/사고
- 중복 주제는 1개로 압축(같은 사건은 하나만 선택)
- 너무 사소/지역/포토성은 제외

[출력 형식]
- 반드시 JSON만 출력
- 스키마:
  {{
    "editorial_summary": "최근 {days}일 핵심을 2~3문장으로",
    "selected": [
      {{"type":"group|article","id":"...","reason":"선정 이유 1문장"}},
      ...
    ]
  }}
- selected는 최대 {top_k}개이며, id는 반드시 후보에 있는 것만 사용.

[후보 목록]
{catalog}
"""
    out = _call_gemini(client_info, contents, min_interval, call_label="highlights_select")
    if not out:
        return None
    try:
        import json
        text = out.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        obj = json.loads(text[start:end])
        selected = obj.get("selected") or []
        if not isinstance(selected, list):
            selected = []
        allowed = {(c.get("type"), c.get("id")) for c in cand}
        cleaned = []
        for it in selected:
            if not isinstance(it, dict):
                continue
            t = (it.get("type") or "").strip()
            i = (it.get("id") or "").strip()
            if (t, i) not in allowed:
                continue
            cleaned.append({
                "type": t,
                "id": i,
                "reason": (it.get("reason") or "").strip()[:200],
            })
            if len(cleaned) >= top_k:
                break
        return {
            "days": days,
            "top_k": top_k,
            "editorial_summary": (obj.get("editorial_summary") or "").strip()[:600],
            "selected": cleaned,
        }
    except Exception as e:
        logger.warning("highlights_select parse failed: %s", e)
        return None


def merge_summaries(client_info, articles: list, min_interval: float = 1.0) -> Optional[str]:
    if not client_info or not articles:
        return None
    parts = []
    for i, a in enumerate(articles[:10], 1):
        parts.append(f"[기사{i}] 제목: {getattr(a, 'title', '')}\n요약/본문: {(getattr(a, 'summary', '') or getattr(a, 'body_snippet', ''))[:1500]}")
    combined = "\n\n".join(parts)
    contents = f"""아래는 같은 사건을 다룬 여러 기사입니다. 가장 많은 정보를 담은 하나의 통합 요약으로 정리해 주세요.
중복된 사실은 한 번만, 서로 다른 관점·수치·출처·세부 내용은 빠짐없이 포함하세요. 5문장 이내.

{combined}
"""
    out = _call_gemini(client_info, contents, min_interval, call_label="merge_summaries")
    return out[:2000] if out else None


def _strip_leading_title_from_merged_content(text: str) -> str:
    """통합 내용 앞쪽의 ## 제목, **제목** 등 헤더를 제거해 본문부터 보이게 함."""
    if not text or not text.strip():
        return text
    s = text.strip()
    # ## 제목 또는 ### 제목 (한 줄) 제거
    if s.startswith("##"):
        idx = s.find("\n")
        if idx != -1:
            s = s[idx + 1 :].lstrip()
        else:
            s = s.lstrip("#").strip()
    # **제목** (한 줄) 제거
    if s.startswith("**"):
        end = s.find("**", 2)
        if end != -1 and (end + 2 >= len(s) or s[end + 2 : end + 3] in "\n\r"):
            s = s[end + 2 :].lstrip()
        elif end != -1:
            rest = s[end + 2 :].lstrip()
            if rest.startswith("\n"):
                s = rest.lstrip()
    return s.strip() or text


# 통합한 내용: LLM 출력·입력 자르지 않도록 상한을 크게 둠 (실질상 전체 반영)
_MERGE_CONTENT_BODY_MAX = 100000
_MERGE_CONTENT_OUTPUT_MAX = 100000
_MERGE_FACTS_INPUT_MAX = 80000  # 1단계 추출 결과 합쳐서 2단계에 넣을 때 상한


def _extract_facts_from_articles(client_info, articles: list, min_interval: float) -> Optional[str]:
    """1단계: 각 기사에서 정보 조각을 추출해 합집합 작성의 입력으로 쓸 구조화 텍스트 반환 (사람이 분석하듯)."""
    if not client_info or not articles:
        return None
    parts = []
    for i, a in enumerate(articles[:10], 1):
        body = getattr(a, "body_snippet", "") or getattr(a, "summary", "") or ""
        title = getattr(a, "title", "") or ""
        parts.append(f"[기사{i}] 제목: {title}\n본문: {body[:_MERGE_CONTENT_BODY_MAX]}")
    combined = "\n\n".join(parts)
    contents = f"""아래는 **같은 사건을 다룬 여러 기사**입니다. 사람이 기사를 분석하듯, **각 기사에서 정보 조각을 빠짐없이 추출**해 주세요.

【출력 형식】각 기사마다 반드시 다음 항목을 채워 주세요. 해당 항목에 내용이 없으면 "없음"이라고 적어 주세요.
- 날짜·시점·일정:
- 장소·대회·행사명:
- 인물·기관·회사:
- 수치·지표·금액:
- 발언·인용·입장:
- 배경·추가 맥락:

【규칙】
1) 기사 번호 [기사1], [기사2] ... 로 구분해, **모든 기사**에 대해 위 항목을 채우세요.
2) 원문에 있는 정보를 **빠짐없이** 옮기세요. 요약하지 말고 사실 그대로 나열하세요.
3) 제목·매체명은 출력하지 말고, 위 항목만 텍스트로 출력하세요.

{combined}
"""
    out = _call_gemini(client_info, contents, min_interval, call_label="merge_extract_facts")
    return (out or "").strip()[: _MERGE_FACTS_INPUT_MAX] or None


def _write_merged_narrative_from_facts(client_info, facts_text: str, min_interval: float) -> Optional[str]:
    """2단계: 정보 조각 합집합을 바탕으로 하나의 연속된 본문으로 작성 (중복 제거, 순서·문단 정리)."""
    if not client_info or not (facts_text or "").strip():
        return None
    contents = f"""아래는 **같은 사건을 다룬 여러 기사의 정보 조각(합집합)**입니다. 이 조각들을 바탕으로 **하나의 본문**을 작성해 주세요.

【원칙】
- **합집합**: 여러 기사에 나온 정보를 **하나도 빠짐없이** 반영하세요. 한 기사에만 있는 날짜·장소·인물·수치·인용도 모두 포함하세요.
- **중복 제거**: 동일한 사실이 반복되면 한 번만 서술하세요.
- **일관된 서사**: 시간순·중요도순 등 읽기 쉬운 순서로 문단을 구성하세요.

【형식】
- **15문장 이상, 800자 이상**으로 작성하세요.
- **문단 구분**: 2~3문장마다 또는 주제가 바뀔 때마다 **빈 줄(줄바꿈 두 번)**을 넣어 주세요.
- **출력**: ##, **, 헤드라인, 제목 없이 **첫 문장부터 본문 내용**으로 바로 시작하세요. (예: "○○가 12일 발표에 따르면…")

【정보 조각】
{facts_text}
"""
    out = _call_gemini(client_info, contents, min_interval, call_label="merge_write_narrative")
    return (out or "").strip()[: _MERGE_CONTENT_OUTPUT_MAX] or None


def extract_event_identifier(
    client_info,
    title: str,
    summary_or_body: str,
    min_interval: float = 1.0,
) -> Optional[str]:
    """기사 제목·요약/본문에서 '같은 사건인지' 판별할 수 있는 짧은 식별 문구만 추출. 사람이 보는 관점의 핵심(날짜·행사·인물·주제)만 남김."""
    if not client_info or not (title or "").strip():
        return None
    text = ((summary_or_body or "").strip() or "")[:1500]
    contents = f"""다음 뉴스가 **다루는 사건을 한 줄로 식별하는 문구**를 만들어 주세요.

【목적】다른 매체 기사와 "같은 뉴스인지" 비교할 때 쓸 식별자입니다. 표현이 달라도 같은 사건이면 비슷한 식별자가 나와야 합니다.

【규칙】
- **회의·정상회담**이면 반드시 "제N차 ○○ 회의" 형식으로 통일하세요. 예: "제10차 한일 재무장관 회의", "제5차 한미 정상회담"
- **대회·행사**면 "연도·대회명·라운드/일정"을 넣으세요. 예: "2026 리쥬란 챔피언십 3R"
- 날짜·시점(가능하면), 행사/회의 이름, 핵심 주제만. "[포토]", " - 매체명"은 넣지 마세요.
- 50자 이내. 예: "제10차 한일 재무장관 회의, 통화·외환시장 공조"

제목: {title}
본문 요약/일부: {text}

식별 문구만 한 줄로 출력하세요. 설명 없이."""

    out = _call_gemini(client_info, contents, min_interval, call_label="event_identifier")
    if not out:
        return None
    return out.strip()[:200] or None


def are_same_event(
    client_info,
    title1: str,
    summary1: str,
    title2: str,
    summary2: str,
    min_interval: float = 1.0,
) -> bool:
    """두 기사가 **같은 사건**을 다루는지 사람처럼 판단. 제목만 다른 표현이어도 같은 사건이면 True."""
    if not client_info:
        return False
    s1 = (summary1 or "")[:800]
    s2 = (summary2 or "")[:800]
    contents = f"""아래 두 뉴스가 **같은 사건(동일한 뉴스)**을 다루는지 판단하세요.
- 같은 행사·발표·인물·이슈를 다루면 같은 사건입니다. 제목·매체가 달라도 내용이 같으면 "예"로 답하세요.
- 포토/카드 등 형식만 다르고 같은 경기·회의·발표면 같은 사건입니다. 애매하면 같은 사건으로 보는 편으로 판단하세요.

【기사 A】
제목: {title1}
요약/본문: {s1}

【기사 B】
제목: {title2}
요약/본문: {s2}

같은 사건이면 "예", 전혀 다른 사건이면 "아니오"만 한 줄로 답하세요."""

    out = _call_gemini(client_info, contents, min_interval, call_label="are_same_event")
    if not out:
        return False
    out = out.strip().upper()
    return "예" in out or "YES" in out or "같" in out or "동일" in out


def _ensure_paragraph_breaks(text: str) -> str:
    """통합한 내용이 한 줄로 나오지 않도록, 문장 단위로 2~3문장마다 줄바꿈 삽입."""
    if not text or "\n\n" in text or text.count("\n") >= 3:
        return text
    # 문장 끝(. 。) 기준으로 분리
    parts = re.split(r"(?<=[.。])\s+", text)
    if len(parts) <= 1:
        return text
    out = []
    for i, p in enumerate(parts):
        p = p.strip()
        if not p:
            continue
        out.append(p)
        if (i + 1) % 2 == 0 and i + 1 < len(parts):
            out.append("")
    return "\n\n".join(out).strip()


def merge_content(
    client_info,
    articles: list,
    min_interval: float = 1.0,
    merge_union_style: bool = False,
) -> Optional[str]:
    """여러 기사 내용을 합집합으로 하나의 본문으로 통합.
    merge_union_style=True면 2단계(정보 추출 → 합집합 서사 작성)로 사람 분석처럼 병합. 권장."""
    if not client_info or not articles:
        return None

    if merge_union_style:
        facts = _extract_facts_from_articles(client_info, articles, min_interval)
        if not facts:
            merge_union_style = False
        else:
            out = _write_merged_narrative_from_facts(client_info, facts, min_interval)
            if out:
                out = _strip_leading_title_from_merged_content(out)
                out = _ensure_paragraph_breaks(out)
                return out[:_MERGE_CONTENT_OUTPUT_MAX] if out else None

    # 단일 프롬프트 병합 (기존 방식)
    parts = []
    for i, a in enumerate(articles[:10], 1):
        body = getattr(a, "body_snippet", "") or getattr(a, "summary", "") or ""
        parts.append(f"[기사{i}] 제목: {getattr(a, 'title', '')}\n본문: {body[:_MERGE_CONTENT_BODY_MAX]}")
    combined = "\n\n".join(parts)
    contents = f"""아래는 같은 사건을 다룬 여러 기사입니다. '통합한 내용'은 **여러 뉴스의 내용을 최대한 합집합**으로 담은 하나의 본문입니다.
- 각 기사에 있는 내용을 빠짐없이 합쳐 주세요. 중복된 사실은 한 번만, 서로 다른 정보·인용·수치·배경·인물·일정은 모두 포함해 하나의 긴 본문으로 이어서 작성하세요.
- 반드시 15문장 이상, 800자 이상으로 작성하세요.
- **문단 구분**: 2~3문장마다 또는 주제가 바뀔 때마다 **빈 줄(줄바꿈 두 번)**을 넣어 문단을 나누어 주세요. 한 줄로 쭉 이어지지 않게 해 주세요.
- **출력 규칙**: 
  1) 기사 제목·"[기사1]"·매체명은 출력하지 마세요.
  2) ##, **, 헤드라인, 제목 형식 없이 **첫 문장부터 본문 내용**으로 바로 시작하세요. (예: "○○기업이 12일 발표에 따르면…"처럼)

{combined}
"""
    out = _call_gemini(client_info, contents, min_interval, call_label="merge_content")
    if not out:
        return None
    out = _strip_leading_title_from_merged_content(out)
    out = _ensure_paragraph_breaks(out)
    return out[:_MERGE_CONTENT_OUTPUT_MAX] if out else None
