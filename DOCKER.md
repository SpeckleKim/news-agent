# Docker 실행

**한 컨테이너**로 웹 서버(6800) + 15분 수집 스케줄러가 함께 동작합니다.

## 환경 변수 (서버에서 설정)

- `GOOGLE_AI_API_KEY` – Gemini API 키
- `GNEWS_API_KEY` – GNews API 키 (선택)
- `WEB_PASSWORD` – 피드/검색 로그인 비밀번호

## 빌드 및 실행

```bash
# 이미지 빌드
docker compose build

# 백그라운드 실행 (DB는 news_data 볼륨에 저장)
docker compose up -d

# 로그 확인
docker compose logs -f
```

브라우저: `http://서버IP:6800/` → 로그인 후 피드/검색 사용.

## 중지

```bash
docker compose down
# DB 유지: down 만 하면 볼륨은 남음
# DB까지 삭제: docker compose down -v
```
