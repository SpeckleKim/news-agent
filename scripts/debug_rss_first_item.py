#!/usr/bin/env python3
"""RSS에서 첫 번째 항목이 어떤 값으로 오는지 확인 (body_snippet 원인 분석용)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser

# config에서 첫 번째 Google News RSS 사용
URL = "https://news.google.com/rss/search?q=AI+finance+when:1h&hl=ko&gl=KR&ceid=KR:ko"

def main():
    print("Fetching:", URL)
    parsed = feedparser.parse(URL)
    entries = getattr(parsed, "entries", [])
    if not entries:
        print("No entries.")
        return
    entry = entries[0]
    print("\n=== 첫 번째 entry 속성 목록 ===")
    print(list(entry.keys()))
    print("\n=== title ===")
    print(repr(entry.get("title")))
    print("\n=== link ===")
    print(repr(entry.get("link")))
    print("\n=== summary (우리 body_snippet에 들어가는 값) ===")
    s = getattr(entry, "summary", None) or entry.get("summary")
    print(repr(s)[:500] if s else "None")
    if s and len(s) > 500:
        print("... (length:", len(s), ")")
    print("\n=== description ===")
    d = getattr(entry, "description", None) or entry.get("description")
    print(repr(d)[:500] if d else "None")
    if d and len(d) > 500:
        print("... (length:", len(d), ")")
    print("\n=== content (있으면) ===")
    c = getattr(entry, "content", None) or entry.get("content")
    if c:
        print(type(c), c[0] if isinstance(c, list) else c)
    else:
        print("None")
    print("\n=== 결론: RSS가 준 '본문'에 해당하는 필드 ===")
    print("우리는 summary 또는 description을 body_snippet으로 씀. 위 값이 그대로 DB body_snippet에 들어감.")

if __name__ == "__main__":
    main()
