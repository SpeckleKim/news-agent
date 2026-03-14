# 뉴스 수집 AI 에이전트 — 프로그래밍 계획

이 문서는 [DESIGN.md](./DESIGN.md) 설계를 기준으로 **단계별 구현 계획**을 정리한 것입니다.

---

## Phase 0: 환경 준비 (1일차)

### 0.1 저장소 초기화
- [ ] 프로젝트 루트에 `news_agent` 패키지 및 `src/` 구조 생성
- [ ] `requirements.txt` 작성 (아래 참고)
- [ ] `.env.example` 작성: `GOOGLE_AI_API_KEY`, `GNEWS_API_KEY`, **`WEB_PASSWORD`**(뉴스 페이지 접근용) 등
- [ ] `.gitignore`: `data/`, `.env`, `__pycache__`, `*.pyc`, 가상환경

### 0.2 의존성 (requirements.txt 초안)

```
# 스케줄링
apscheduler>=3.10.0

# 설정
pyyaml>=6.0

# 뉴스 수집
feedparser>=6.0.0
requests>=2.28.0

# Google AI (Gemini)
google-genai>=1.0.0

# 웹 UI
fastapi>=0.100.0
uvicorn[standard]>=0.22.0

# 유틸
python-dotenv>=1.0.0
```

### 0.3 검증
- [ ] 가상환경 생성 후 `pip install -r requirements.txt`
- [ ] `python -c "from google import genai; print('OK')"` 로 SDK 동작 확인

---

## Phase 1: 설정·모델·저장소 (2일차)

### 1.1 설정 로드 (`src/config.py`)
- [ ] `config.yaml` 스키마 정의 (schedule, sources, google_ai, storage, dedup)
- [ ] YAML 로드 + 환경변수 치환 (`api_key_env` → 실제 API 키)
- [ ] 단일 설정 객체 반환 (dataclass 또는 SimpleNamespace)
- [ ] (선택) **hot-reload**: config 파일 변경 감지 시 다음 수집 주기부터 새 설정 적용

### 1.2 데이터 모델 (`src/models/article.py`)
- [ ] `Article` dataclass: id, url, url_hash, title, summary, body_snippet, source, published_at, collected_at, keywords, category, duplicate_group_id, version
- [ ] `DuplicateGroup` dataclass: id, canonical_article_id, merged_summary, merged_title, source_article_ids, source_urls, created_at, updated_at, merge_status
- [ ] `RelatedChain` dataclass: id, article_ids (시간순), topic_label, created_at, updated_at — 연관 뉴스 히스토리(새 뉴스이지만 이전 뉴스와 연관된 후속/같은 주제)용
- [ ] Article / DuplicateGroup / RelatedChain ↔ dict 변환 (DB 입출력용)

### 1.3 저장소 (`src/storage/repository.py`)
- [ ] SQLite 연결, 테이블 생성 (articles, duplicate_groups, **related_chains**)
- [ ] **기사**: `insert_article`, `update_article`, `get_by_url_hash`, `get_recent_titles(days)`, `list_latest(limit, offset)`, `get_article(id)`
- [ ] **그룹**: `insert_group`, `update_group`, `get_group(id)`, `list_groups(limit, offset)`, `add_article_to_group`, `remove_article_from_group`
- [ ] **연관 체인**: `insert_chain`, `update_chain`, `get_chain(id)`, `get_chains_for_article(article_id)` → 해당 기사가 속한 체인 목록 + 각 체인 내 이전/다음 기사 위치, `add_article_to_chain(chain_id, article_id)` (시간순 삽입)
- [ ] **수정 지원**: `update_article` 시 title/summary/keywords/category 변경 가능, version 증가. `update_group` 시 merged_summary, merge_status(edited) 갱신
- [ ] 인덱스: url_hash, published_at, collected_at, duplicate_group_id

---

## Phase 2: 수집기 (3일차)

### 2.1 수집기 인터페이스 (`src/collectors/base.py`)
- [ ] `BaseCollector` 추상 클래스: `collect(keywords: list[str]) -> list[RawArticle]`
- [ ] `RawArticle`: url, title, body_snippet, source, published_at 등 수집 단계용 최소 필드

### 2.2 GNews 수집기 (`src/collectors/gnews.py`)
- [ ] GNews API 호출 (키워드별 검색 또는 통합 쿼리)
- [ ] 응답 파싱 → `RawArticle` 리스트 반환
- [ ] rate limit·에러 처리 (재시도, 로그)

### 2.3 RSS 수집기 (`src/collectors/rss.py`)
- [ ] feedparser로 RSS URL에서 엔트리 추출
- [ ] 제목/링크/요약/날짜 → `RawArticle` 변환
- [ ] AI·금융 관련 RSS URL 예시를 config 또는 문서에 명시

### 2.4 수집기 팩토리 (`src/collectors/__init__.py`)
- [ ] config의 `sources` 순회하며 타입별 인스턴스 생성
- [ ] `run_all_collectors(config) -> list[RawArticle]` (중복 URL은 한 번만)

---

## Phase 3: 파이프라인 — 정규화·중복·Gemini (4~5일차)

### 3.1 정규화 (`src/pipeline/normalize.py`)
- [ ] URL 정규화 (트래킹 파라미터 제거, 스킴 통일)
- [ ] `url_hash = hashlib.sha256(normalized_url.encode()).hexdigest()[:16]`
- [ ] RawArticle → Article 초안 생성 (id, collected_at 설정, summary/body_snippet는 빈 값 가능)

### 3.2 중복 탐지 및 통합 그룹 생성 (`src/pipeline/dedup.py`)
- [ ] **URL 기준**: `get_by_url_hash`로 기존 존재 시 → “갱신” 경로로 표시
- [ ] **제목 유사도**: 최근 N일 제목 목록 가져와서 새 기사 제목과 비교 (Jaccard/Levenshtein 또는 Gemini 질의)
- [ ] **통합 그룹 생성**: 중복 후보끼리 또는 기존 그룹과 매칭 시 → DuplicateGroup 생성 또는 기존 그룹에 추가
- [ ] **병합 요약**: 그룹 내 모든 기사 제목·요약·본문 일부를 Gemini에 넣고 **"가장 많은 정보를 담은 하나의 통합 요약으로 정리. 중복 사실은 한 번만, 서로 다른 관점·수치·출처·세부 내용은 빠짐없이 포함"** 하여 merged_summary 생성. 재병합 시에도 동일 (merge_status가 `edited`인 경우 덮어쓸지 옵션 처리)
- [ ] 출력: `(new_articles, to_update_by_url_hash, new_or_updated_groups)`

### 3.2b 연관 뉴스(히스토리) 탐지 및 체인 생성 (`src/pipeline/related.py` 또는 dedup 내)
- [ ] **연관 탐지**: 신규/갱신 기사 저장 후, 키워드·카테고리·엔티티 겹침으로 후보 기사 추린 뒤 **Gemini에 "이 기사가 아래 기사들 중 어떤 것의 후속/연관인가? 같은 흐름인가?"** 질의해 연관 여부·순서 판단. 또는 키워드 유사 + 시간순으로 같은 주제 체인에 추가
- [ ] **체인 생성/갱신**: 연관이 있으면 기존 RelatedChain에 해당 기사(또는 그룹 대표 id)를 **published_at 시간순**으로 삽입. 없으면 새 RelatedChain 생성. 중복 그룹은 체인에 대표 1건만 포함
- [ ] 저장소: `add_article_to_chain`, `insert_chain` 호출

### 3.3 Gemini 연동 (`src/pipeline/gemini_processor.py`)
- [ ] `google-genai` 클라이언트 초기화 (api_key from config)
- [ ] `summarize(text: str) -> str`: 본문 요약 (길이 제한 후 프롬프트)
- [ ] `classify_and_keywords(title: str, body: str) -> dict`: category, keywords 반환
- [ ] `merge_summaries(articles: list[Article]) -> str`: **가장 많은 정보를 담은 하나의 통합 요약** (중복 사실 한 번만, 서로 다른 관점·수치·출처·세부 내용 포함). 연관 판단용 `is_related_followup(new_article, candidate_articles) -> (bool, index?)` (선택)
- [ ] 토큰 한도·실패 시 None 반환 및 로그

### 3.4 파이프라인 오케스트레이션
- [ ] `run_pipeline(config)` 흐름:
  1. 모든 수집기 실행 → RawArticle 리스트
  2. 정규화 → Article 초안 리스트
  3. 저장소와 비교하여 중복 탐지 → **그룹 생성/기존 그룹에 추가**
  4. 신규/갱신 기사에 대해 Gemini 요약·분류 호출
  5. **중복 그룹마다 Gemini 병합 요약 생성(가장 많은 정보 통합)·재병합** → duplicate_groups 테이블에 저장/갱신
  6. **연관 뉴스 탐지 및 RelatedChain 생성/갱신** (같은 사건이 아닌 연관/후속 보도 연결)
  7. 저장소에 insert/update 반영

---

## Phase 4: 스케줄러·진입점 (6일차)

### 4.1 메인 진입점 (`src/main.py`)
- [ ] 설정 로드, 로깅 설정
- [ ] `job()`: `run_pipeline(config)` 한 번 실행
- [ ] APScheduler `BackgroundScheduler` 또는 `BlockingScheduler` 사용
- [ ] `interval_minutes` 또는 cron 표현으로 1시간마다 `job` 실행
- [ ] SIGINT/SIGTERM 시 스케줄러 종료

### 4.2 CLI (선택)
- [ ] `python -m src.main` → 스케줄러 기동
- [ ] `python -m src.main --once` → 1회만 수집·파이프라인 실행 (테스트용)

---

## Phase 5: 설정·키워드 확장 및 문서 (7일차)

### 5.1 기본 config.yaml
- [ ] DESIGN.md에 맞는 `config.yaml` 작성
- [ ] 키워드: 미래에셋증권, 증권사 AI, ChatGPT, Claude, Financial AI, IB AI, AX, DX 등
- [ ] RSS 소스 1~2개 추가 (예: 기술/금융 뉴스 RSS)

### 5.2 README.md
- [ ] 프로젝트 목적, 설계 문서 링크
- [ ] 설치 방법, `.env` 설정, 실행 방법
- [ ] **키워드/소스/수집 주기 변경**: config.yaml의 어느 섹션을 수정하면 되는지 명시 (빠짐 없이 수정 가능하도록)
- [ ] 웹 UI 실행 방법 (uvicorn), 목록/상세/수정 사용법

### 5.3 테스트 (선택)
- [ ] `tests/test_dedup.py`: URL 해시, 제목 유사도, 그룹 생성/재병합 시나리오
- [ ] `tests/test_normalize.py`: URL 정규화 테스트
- [ ] 수집기·Gemini는 모의(mock) 또는 통합 테스트로 일부만

---

## Phase 6: 웹 UI — 조회·수정 (8~9일차)

웹 페이지에서 뉴스와 통합 정보를 **쉽게 보고**, 필요 시 **수정**할 수 있도록 한다. **비밀번호 입력 후 접근**, **다중 기기 동시 접속**(새 기기 로그인 시 이전 기기 끊김 없음), **Docker·포트 6800**을 반영한다.

### 6.1 접근 제어(비밀번호·세션)
- [ ] **비밀번호 설정**: config 또는 환경변수 `WEB_PASSWORD`로 뉴스 페이지 접근용 비밀번호 설정
- [ ] **로그인**: `GET /login` — 비밀번호 입력 폼. `POST /api/auth/login` — 비밀번호 검증 후 **세션 쿠키** 발급 (HttpOnly, Secure 옵션 권장)
- [ ] **다중 기기 동시 접속**: 세션을 **기기별로 별도 발급** (세션 ID는 쿠키에 저장). 새 기기에서 로그인해도 기존 세션을 무효화하지 않음. 세션 저장소: 메모리(dict) 또는 Redis 등
- [ ] **인증 미들웨어/의존성**: `/`, `/articles/*`, `/groups/*`, `/api/feed`, `/api/search`, `/api/articles/*`, `/api/groups/*` 요청 시 세션 검사 → 미인증이면 401 또는 `/login`으로 리다이렉트. `/login`, `POST /api/auth/login`은 인증 제외
- [ ] **로그아웃**: `POST /api/auth/logout` — 해당 기기 세션만 삭제 (다른 기기 세션 유지)

### 6.2 백엔드 API (`src/web/`)
- [ ] FastAPI 앱 생성, 저장소(repository) 주입
- [ ] **목록**: GET `/api/feed` — 그룹 단위 + 단독 기사 혼합, 날짜순. 쿼리: category, keyword, source, since, limit, offset
- [ ] **검색**: GET `/api/search?q=...` — 제목·요약·키워드 검색
- [ ] **기사 상세**: GET `/api/articles/{id}` — 단일 기사 + 소속 그룹 정보(있을 경우) + **관련 뉴스 히스토리**(소속 체인 목록, 각 체인에서 이전/다음 기사 id·제목·날짜)
- [ ] **그룹 상세**: GET `/api/groups/{id}` — 통합 제목·통합 요약·source_urls·소속 기사 목록 + **관련 뉴스 히스토리**(대표 기사 기준으로 동일)
- [ ] **연관 히스토리 전용**: GET `/api/chains/{id}` — 체인 전체 목록(시간순) 반환. 또는 GET `/api/articles/{id}/related-history` 로 이전 보도/후속 보도 목록만 반환
- [ ] **기사 수정**: PATCH `/api/articles/{id}` — title, summary, keywords, category 수정 → repository.update_article, version 증가
- [ ] **그룹 수정**: PATCH `/api/groups/{id}` — merged_summary 수정 시 merge_status=edited, (선택) 그룹에서 기사 제외/추가

### 6.3 프론트(웹 페이지)
- [ ] **목록(피드)**: 그룹이면 통합 제목 + 통합 요약 + "원문 N개" 링크; 단독이면 제목 + 요약 + 원문 1개. 카드/리스트 레이아웃
- [ ] **필터**: 카테고리, 키워드 태그, 기간, 출처 선택 시 목록 API 쿼리로 반영
- [ ] **검색창**: 입력 시 `/api/search` 호출 후 결과 렌더링
- [ ] **기사 상세 페이지**: 제목, 요약, 본문 일부, 원문 링크, 키워드, 카테고리 + **편집** 버튼 + **관련 뉴스 히스토리** — 이전 보도 / 후속 보도 링크 또는 타임라인. 클릭 시 해당 기사/그룹 상세로 이동, 체인 따라가기 가능
- [ ] **그룹 상세 페이지**: 통합 제목, 통합 요약, "같은 뉴스로 묶인 기사" 목록(제목, 출처, 링크) + **통합 요약 편집** + **관련 뉴스 히스토리** — 동일하게 이전/후속 보도 따라가기
- [ ] **로그인 페이지**: 비밀번호 입력 폼 → POST `/api/auth/login` 후 성공 시 피드로 이동. 미인증 사용자가 보호된 경로 접근 시 로그인 페이지로 리다이렉트
- [ ] 정적 HTML + Alpine.js 또는 Vanilla JS, 또는 React/Vue 등 (선택). **상세 설계: [FRONTEND_DESIGN.md](./FRONTEND_DESIGN.md)**

### 6.4 실행·의존성
- [ ] `requirements.txt`에 `fastapi`, `uvicorn`, (선택) `jinja2` 추가. **세션**: 서버 메모리만 쓸 경우 추가 패키지 없음; Redis 사용 시 `redis` 등 추가
- [ ] `uvicorn` 바인드: 컨테이너 내부에서는 `0.0.0.0:6800`으로 리스닝하여 외부에서 포트 6800으로 접근 가능하게 함
- [ ] README에 "웹으로 보기", "비밀번호 설정", "다중 기기 접속" 섹션 추가

### 6.5 Docker 배포
- [ ] **Dockerfile**: Python 3.10+ 베이스, `requirements.txt` 설치, `src/`, `config.yaml` 복사, CMD로 웹+스케줄러 동시 실행(또는 단일 프로세스로 uvicorn + 백그라운드 스케줄러)
- [ ] **docker-compose.yml**: 서비스 1개(뉴스 에이전트). **포트**: `6800:6800` (호스트 6800 → 컨테이너 6800). **볼륨**: `./data` → 컨테이너 내 데이터 경로(SQLite 영속화), (선택) `./config.yaml` 마운트
- [ ] **환경변수**: `GOOGLE_AI_API_KEY`, `GNEWS_API_KEY`, `WEB_PASSWORD` 등은 `env_file: .env` 또는 `environment`로 주입
- [ ] `.dockerignore`: `data/`, `.env`, `__pycache__`, `.git` 등 제외
- [ ] README에 `docker-compose up -d`, 접속 주소 `http://<서버>:6800` 안내

---

## Phase 7: 개선·확장 (이후)

- [ ] **중복 판단에 Gemini 활용**: “두 제목이 같은 사건인가?” 질의로 정확도 향상
- [ ] **임베딩 기반 유사도**: Gemini embedding 또는 sentence-transformers로 벡터 저장·코사인 유사도
- [ ] **알림**: 중요 키워드 매칭 시 슬랙/이메일 전송
- [ ] **설정 웹 UI**: 키워드 추가/삭제, 소스 on/off를 웹에서 수정 후 config 반영 또는 DB 설정
- [ ] **수정 이력**: article_edits / group_edits 테이블로 변경 이력 추적
- [ ] **에러·재시도**: 수집/API 실패 시 재시도, Dead letter 로그

---

## 일정 요약

| Phase | 내용 | 예상 일수 |
|-------|------|-----------|
| 0 | 환경·의존성·폴더 구조 | 0.5 |
| 1 | 설정, 모델, SQLite 저장소(기사+그룹, 수정 API 지원) | 1 |
| 2 | 수집기 (GNews, RSS) | 1 |
| 3 | 정규화, 중복 탐지, **통합 그룹 생성/재병합**, Gemini | 2 |
| 4 | 스케줄러, main | 0.5 |
| 5 | config·README·키워드/소스 수정 방법 문서화 | 0.5 |
| 6 | **웹 UI** (목록/필터/검색/상세/기사·그룹 수정) + **비밀번호·세션(다중 기기)** + **Docker(포트 6800)** | 2 |
| 7 | 개선 (선택) | - |

**합계: 약 7~8일** (테스트·디버깅 여유 포함 시 1.5주 권장)

---

## 구현 순서 체크리스트 (한 줄 요약)

1. 프로젝트 구조·requirements·.env.example
2. config 로드(선택 hot-reload), Article+DuplicateGroup 모델, SQLite 저장소(그룹 CRUD·수정 지원)
3. BaseCollector, GNews, RSS 수집기
4. URL 정규화, url_hash, dedup + **통합 그룹 생성/재병합(가장 많은 정보)** + **연관 뉴스 체인(히스토리) 생성**
5. Gemini 요약·분류·**통합 병합 요약(최대 정보)** ·(선택) 연관 판단
6. 파이프라인 합치기 (수집 → 정규화 → dedup → Gemini → 저장 → **연관 체인 갱신**)
7. main + APScheduler (1시간 주기)
8. config.yaml, README(키워드/소스 수정 방법·웹 실행법)
9. **웹: FastAPI 목록/검색/상세/수정 API + 프론트 목록·필터·상세·편집** + **관련 뉴스 히스토리 API·UI**(이전/후속 보도 따라가기)
10. **웹 접근 제어**: 비밀번호 로그인, 세션(다중 기기 동시 접속), 로그인 페이지·미들웨어
11. **Docker**: Dockerfile, docker-compose, 포트 6800, 볼륨·env

이 순서대로 진행하면 설계서(DESIGN.md)와 일치하는 **수정 가능·중복 통합·웹 조회**를 갖춘 뉴스 수집 AI 에이전트를 단계적으로 완성할 수 있습니다.

---

## 참고: 피드에서 같은 뉴스만 보일 때

- **수집 소스**: `config.yaml`의 `sources`에 RSS/API 소스를 여러 개 두면 주제가 다양해집니다. 한 소스만 있으면 비슷한 기사만 수집될 수 있습니다.
- **중복 그룹화**: `dedup.title_similarity_threshold`가 너무 높으면 서로 다른 이슈가 한 그룹으로 묶일 수 있고, 너무 낮으면 그룹이 거의 생기지 않아 피드가 단일 기사 위주로 보일 수 있습니다. (현재 기본 0.88)
- **피드 목록**: API는 그룹·단일 기사를 합친 뒤 `published_at`·`importance` 기준으로 정렬하고, `limit`/`offset`으로 페이지를 잘라 반환합니다. 같은 8건만 반복되면 `offset`이 적용되는지 확인하세요.
