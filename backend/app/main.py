from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .core.config import AppSettings, get_settings
from .db import repository
from .db.database import create_db_engine, initialize_database
from .services.credentials import CredentialStore
from .services.event_bus import EventBus
from .services.worker import BookingWorkerManager


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def create_app(settings: AppSettings | None = None) -> FastAPI:
    config = settings or get_settings()
    engine = create_db_engine(config.database_url, config.data_dir)
    event_bus = EventBus()
    credential_store = CredentialStore(config)
    worker = BookingWorkerManager(engine, config, event_bus, credential_store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_database(engine)
        repository.mark_interrupted_reservations(engine)
        yield
        await worker.shutdown()

    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description="개인용 KTX 좌석 조회·예약 보조 백엔드",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = config
    app.state.engine = engine
    app.state.event_bus = event_bus
    app.state.credential_store = credential_store
    app.state.worker = worker
    app.include_router(router)
    if FRONTEND_DIST.joinpath("index.html").exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app


app = create_app()
