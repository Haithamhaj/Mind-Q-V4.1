from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api import router as api_router
from .deps import log_request

app = FastAPI(title="Phase-10 BI MVP v2")
app.middleware("http")(log_request)
app.include_router(api_router)
app.mount("/static", StaticFiles(directory="bi10/web/static"), name="static")
templates = Jinja2Templates(directory="bi10/web/templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request, "dir": "rtl"})


@app.get("/explorer", response_class=HTMLResponse)
def explorer(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("explorer.html", {"request": request, "dir": "rtl"})


__all__ = ["app"]
