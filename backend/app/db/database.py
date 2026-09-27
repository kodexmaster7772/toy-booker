from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from .models import AutomationSettings


def create_db_engine(database_url: str, data_dir: Path) -> Engine:
    data_dir.mkdir(parents=True, exist_ok=True)
    return create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )


def initialize_database(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if session.exec(select(AutomationSettings).where(AutomationSettings.id == 1)).first() is None:
            session.add(AutomationSettings())
            session.commit()

