"""FastAPI 앱: API 라우트, 정적 파일 서빙."""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import get_session_id, is_valid_session
from .routes import api_router

app = FastAPI(title="뉴스 에이전트")
app.include_router(api_router, prefix="/api", tags=["api"])

# 프로토타입 정적 파일 (프로젝트 루트 기준)
PROTOTYPE_ROOT = Path(__file__).resolve().parent.parent.parent / "prototype"
if PROTOTYPE_ROOT.exists():
    app.mount("/static", StaticFiles(directory=str(PROTOTYPE_ROOT)), name="static")


@app.get("/")
async def index(request: Request):
    """메인 = 피드. 로그인 안 되어 있으면 로그인 페이지로."""
    if not get_session_id(request) or not is_valid_session(get_session_id(request)):
        return RedirectResponse("/login", status_code=302)
    return FileResponse(PROTOTYPE_ROOT / "feed.html")


@app.get("/login")
@app.get("/login.html")
async def login_page(request: Request):
    """이미 로그인된 상태면 메인(/)으로."""
    sid = get_session_id(request)
    if sid and is_valid_session(sid):
        return RedirectResponse("/", status_code=302)
    return FileResponse(PROTOTYPE_ROOT / "login.html")


@app.get("/feed.html")
async def feed_page(request: Request):
    if not get_session_id(request) or not is_valid_session(get_session_id(request)):
        return RedirectResponse("/login", status_code=302)
    return FileResponse(PROTOTYPE_ROOT / "feed.html")


@app.get("/major.html")
async def major_page(request: Request):
    if not get_session_id(request) or not is_valid_session(get_session_id(request)):
        return RedirectResponse("/login", status_code=302)
    return FileResponse(PROTOTYPE_ROOT / "major.html")


@app.get("/search.html")
async def search_page(request: Request):
    if not get_session_id(request) or not is_valid_session(get_session_id(request)):
        return RedirectResponse("/login", status_code=302)
    return FileResponse(PROTOTYPE_ROOT / "search.html")


@app.get("/article.html")
async def article_page(request: Request):
    if not get_session_id(request) or not is_valid_session(get_session_id(request)):
        return RedirectResponse("/login", status_code=302)
    return FileResponse(
        PROTOTYPE_ROOT / "article.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/group.html")
async def group_page(request: Request):
    if not get_session_id(request) or not is_valid_session(get_session_id(request)):
        return RedirectResponse("/login", status_code=302)
    return FileResponse(
        PROTOTYPE_ROOT / "group.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


# 정적 리소스 (CSS, JS) — /css, /js 로 접근 시 prototype 하위에서 서빙
@app.get("/css/{path:path}")
async def css(path: str):
    f = PROTOTYPE_ROOT / "css" / path
    if not f.is_file():
        raise HTTPException(404)
    return FileResponse(f)


@app.get("/js/{path:path}")
async def js(path: str):
    f = PROTOTYPE_ROOT / "js" / path
    if not f.is_file():
        raise HTTPException(404)
    return FileResponse(f)
