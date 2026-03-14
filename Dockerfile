# news-agent: 웹 서버 + 15분 스케줄러 (한 컨테이너)
FROM python:3.11-slim

WORKDIR /app

# 의존성만 먼저 설치 (캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 복사 (config, 소스, 프로토타입)
COPY config.yaml .
COPY src ./src
COPY run_web.py .
COPY prototype ./prototype

# 데이터 디렉터리 (볼륨 마운트 시 사용)
RUN mkdir -p /app/data

# 웹 6800, 스케줄러는 같은 프로세스에서 백그라운드
ENV PYTHONUNBUFFERED=1
EXPOSE 6800

CMD ["sh", "-c", "python -m src.main & exec python run_web.py"]
