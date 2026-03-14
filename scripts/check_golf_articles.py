"""김시현/리쥬란 골프 기사가 왜 4개 카드로 나오는지 제목 유사도로 확인."""
import re
import sqlite3
import sys
from difflib import SequenceMatcher

DB_PATH = "data/news.db"

# dedup 모듈과 동일한 로직 사용 (정규화 반영)
def _word_set(text: str) -> set:
    t = (text or "").strip()
    tokens = re.findall(r"[^\s,·\-\[\]()]+", t)
    return set(t for t in tokens if len(t) >= 2)


def _jaccard_char(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_set = set(a.replace(" ", ""))
    b_set = set(b.replace(" ", ""))
    if not a_set and not b_set:
        return 1.0
    return len(a_set & b_set) / len(a_set | b_set) if (a_set | b_set) else 0.0


def _normalize_title_for_similarity(title: str) -> str:
    t = (title or "").strip()
    t = re.sub(r"^\[포토\]\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^\[카드\]\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*-\s*[^\s\-]+\.?(com|co\.kr|net|뉴스|네이트|매일경제|edaily)[^\s]*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*-\s*[^\s\-]+$", "", t).strip()
    return t or title


def title_similarity(t1: str, t2: str) -> float:
    raw1, raw2 = (t1 or "").strip(), (t2 or "").strip()
    if raw1 == raw2:
        return 1.0
    if len(raw1) < 3 or len(raw2) < 3:
        return 0.0
    norm1 = _normalize_title_for_similarity(raw1)
    norm2 = _normalize_title_for_similarity(raw2)
    if norm1 == norm2:
        return 1.0
    def _score(a, b):
        s = [_jaccard_char(a, b)]
        w1, w2 = _word_set(a), _word_set(b)
        if w1 and w2:
            u = len(w1 | w2)
            s.append(len(w1 & w2) / u if u else 0.0)
        s.append(SequenceMatcher(None, a, b).ratio())
        return max(s)
    return max(_score(raw1, raw2), _score(norm1, norm2))


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda c, r: {c.description[i][0]: r[i] for i in range(len(r))}
    rows = conn.execute("""
        SELECT id, title, summary, duplicate_group_id, source
        FROM articles
        WHERE title LIKE ? OR summary LIKE ? OR title LIKE ? OR summary LIKE ?
        ORDER BY collected_at DESC
    """, ("%김시현%", "%김시현%", "%리쥬란%", "%리쥬란%")).fetchall()
    conn.close()

    print("=== 김시현/리쥬란 관련 기사 (제목, 그룹ID) ===\n")
    for r in rows:
        print("id:", r["id"], "| group:", r["duplicate_group_id"])
        print("  title:", (r["title"] or "")[:90])
        print()

    threshold = 0.75
    print("=== 제목 유사도 쌍 (threshold={}) ===\n".format(threshold))
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            t1, t2 = rows[i]["title"] or "", rows[j]["title"] or ""
            sim = title_similarity(t1, t2)
            ok = "O 묶임" if sim >= threshold else "X 안묶임"
            print("{:.3f} {} ".format(sim, ok))
            print("  A:", t1[:72])
            print("  B:", t2[:72])
            print()


if __name__ == "__main__":
    main()
