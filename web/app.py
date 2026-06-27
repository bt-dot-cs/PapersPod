from dotenv import load_dotenv

load_dotenv()  # must run before importing core.queue (DATABASE_URL needed at connector init)

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.routers import admin, credits, episodes, events, ref

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app_: FastAPI):
    from core.queue import app as queue_app
    logger.info("Opening Procrastinate connector")
    async with queue_app.open_async():
        yield
    logger.info("Procrastinate connector closed")


app = FastAPI(title="PapersPod API", version="0.1.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(episodes.router)
app.include_router(events.router)
app.include_router(ref.router)
app.include_router(admin.router)
app.include_router(credits.router)


@app.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "ok"}
