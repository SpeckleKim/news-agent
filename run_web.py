#!/usr/bin/env python3
"""웹 서버 기동 (포트 6800). 스케줄러는 별도 프로세스에서 python -m src.main 실행."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# 웹 서버 기동 전에 .env 로드 (비밀번호 등)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.web.app:app",
        host="0.0.0.0",
        port=6800,
        reload=False,
    )
