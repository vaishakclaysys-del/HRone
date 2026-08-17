from __future__ import annotations

from fastapi import FastAPI 

from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.core.db import Base, engine
from app.core.seed import seed_users

from app.core.config import BASE_DIR, SESSION_SECRET_KEY
from app.routes.interview import router as interview_router
from app.routes.hackathon import router as hackathon_router
from app.routes.pipeline import router as pipeline_router
from app.routes.auth import router as auth_router
from app.routes.admin import router as admin_router
from app.routes.hr import router as hr_router
from app.core.exceptions import (
    starlette_exception_handler,
    fastapi_exception_handler,
)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.db import _migrate_drop_phone_unique, _migrate_add_flow_column

    Base.metadata.create_all(bind=engine)

    _migrate_drop_phone_unique()
    _migrate_add_flow_column()
    
    with Session(engine) as db:
        seed_users(db)

    yield

app = FastAPI(title="HR Hackathon MVP", root_path="/hrone", lifespan=lifespan,)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(interview_router)
app.include_router(hackathon_router)
app.include_router(pipeline_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(hr_router)

app.add_exception_handler(
    StarletteHTTPException,
    starlette_exception_handler,
)

app.add_exception_handler(
    FastAPIHTTPException,
    fastapi_exception_handler,
)