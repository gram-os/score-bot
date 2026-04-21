import os

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from web.auth import NotAuthenticated, admin_router, router as auth_router

app = FastAPI(title="Score Bot Admin")

secret_key = os.environ.get("SECRET_KEY", "changeme")
app.add_middleware(SessionMiddleware, secret_key=secret_key)

app.mount("/static", StaticFiles(directory="web/static"), name="static")

app.include_router(auth_router)
app.include_router(admin_router)


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/auth/login", status_code=302)


@app.get("/")
async def root():
    return RedirectResponse(url="/admin", status_code=302)
