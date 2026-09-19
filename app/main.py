import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db
from app.scheduler import start_scheduler, shutdown_scheduler
from app.api import router as api_router
from app.config import BASE_DIR

templates_dir = BASE_DIR / "app" / "templates"
static_dir = BASE_DIR / "app" / "static"
static_dir.mkdir(exist_ok=True, parents=True)

templates = Jinja2Templates(directory=str(templates_dir))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo database
    init_db()
    # Khởi động scheduler cào dữ liệu tự động
    try:
        start_scheduler()
    except Exception as e:
        print(f"Không thể khởi động scheduler: {e}")
    yield
    shutdown_scheduler()


app = FastAPI(
    title="GitHub Trending Tracker",
    description="Công cụ cào dữ liệu GitHub Trending và thống kê số lần xuất hiện dạng bảng",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
