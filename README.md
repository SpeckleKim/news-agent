# 뉴스 수집 AI 에이전트

AI·증권·금융·IB 뉴스를 수집하고, 중복을 통합·요약해 웹에서 조회하는 에이전트입니다.

- **수집**: RSS, GNews API (config.yaml의 키워드·소스 설정)
- **처리**: URL 정규화, 제목 유사도 기반 중복 그룹, Gemini 요약·분류·통합 요약
- **저장**: SQLite
- **웹**: 비밀번호 로그인 후 피드/검색/기사·그룹 상세 조회

## 설계 문서

- [DESIGN.md](docs/DESIGN.md) — 아키텍처, 데이터 모델, 설정
- [PROGRAMMING_PLAN.md](docs/PROGRAMMING_PLAN.md) — 단계별 구현 계획

## 설치

```bash
cd news_agent
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env에 GOOGLE_AI_API_KEY, (선택) GNEWS_API_KEY, WEB_PASSWORD 설정
```

## 설정 (config.yaml)

- **키워드/소스**: `sources`에 RSS `url`, GNews `api_key_env`·`keywords` 추가·수정
- **수집 주기**: `schedule.interval_minutes` (기본 60)
- **DB 경로**: `storage.path` (기본 `./data/news.db`)
- **웹 비밀번호**: 환경변수 `WEB_PASSWORD` 또는 config `web.password_env`에 지정한 환경변수

## 실행

### 1회 수집 (테스트)

```bash
python -m src.main --once
```

### 스케줄러 (주기 수집)

```bash
python -m src.main
# 기본 60분마다 수집·파이프라인 실행
```

### 웹 서버 (조회용)

```bash
python run_web.py
# http://localhost:6800 접속 후 로그인
```

- 로그인: `WEB_PASSWORD`에 설정한 비밀번호
- 피드/검색/기사·그룹 상세는 로그인 후 이용

## 프로토타입만 볼 때

`prototype/` 폴더를 로컬 서버로 연다:

```bash
cd prototype && python3 -m http.server 8080
# http://localhost:8080 → 목업 데이터로 동작
```

## Docker (선택)

```bash
docker build -t news-agent .
docker run -p 6800:6800 --env-file .env -v $(pwd)/data:/app/data news-agent
```

- 포트 6800으로 웹 접근
- `data/` 볼륨으로 SQLite 영속화
