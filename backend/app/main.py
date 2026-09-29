"""FastAPI application factory.

create_app() allows injecting a database (tests use mongomock-motor);
the default lifespan connects to MongoDB via Motor.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.config import CORS_ORIGINS, MONGO_TIMEOUT_MS, MONGODB_DB, MONGODB_URI

logging.basicConfig(level=logging.INFO)


def create_app(db=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if db is not None:
            app.state.db = db
            yield
            return
        client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=MONGO_TIMEOUT_MS)
        app.state.db = client[MONGODB_DB]
        try:
            await app.state.db["messages"].create_index("project_id")
        except Exception:
            logging.getLogger(__name__).warning("Could not ensure messages index", exc_info=True)
        yield
        client.close()

    app = FastAPI(title="AI PoC Builder", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(projects_router)
    return app


app = create_app()
