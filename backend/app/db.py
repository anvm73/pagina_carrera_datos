from __future__ import annotations

import os
import time
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _default_sqlite_url() -> str:
    db_path = Path(__file__).resolve().parents[1] / "data" / "ce_iccd.db"
    return f"sqlite:///{db_path.as_posix()}"


def build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        if database_url.startswith("postgres://"):
            return "postgresql+psycopg2://" + database_url.removeprefix("postgres://")
        return database_url

    postgres_host = os.getenv("POSTGRES_HOST", "").strip()
    postgres_db = os.getenv("POSTGRES_DB", "").strip()
    postgres_user = os.getenv("POSTGRES_USER", "").strip()
    postgres_password = os.getenv("POSTGRES_PASSWORD", "").strip()
    postgres_port = os.getenv("POSTGRES_PORT", "5432").strip()
    if postgres_host and postgres_db and postgres_user and postgres_password:
        return (
            f"postgresql+psycopg2://{postgres_user}:{postgres_password}"
            f"@{postgres_host}:{postgres_port}/{postgres_db}"
        )

    return _default_sqlite_url()


DATABASE_URL = build_database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine_options: dict[str, object] = {
    "pool_pre_ping": True,
    "future": True,
}
if IS_SQLITE:
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, future=True)
Base = declarative_base()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    if not IS_SQLITE:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def initialize_database() -> None:
    try:
        from app import models  # noqa: F401
    except ModuleNotFoundError:
        import models  # type: ignore # noqa: F401

    retries = max(1, int(os.getenv("DATABASE_CONNECT_RETRIES", "20")))
    retry_delay_s = max(1, int(os.getenv("DATABASE_CONNECT_RETRY_DELAY_S", "2")))
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            ensure_runtime_schema()
            with engine.begin() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                raise
            time.sleep(retry_delay_s)

    if last_error:
        raise last_error


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    if "alumni_profiles" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("alumni_profiles")}
    statements: list[str] = []

    if "image_content_type" not in existing_columns:
        type_sql = "VARCHAR(120)" if engine.dialect.name == "postgresql" else "TEXT"
        statements.append(
            f"ALTER TABLE alumni_profiles ADD COLUMN image_content_type {type_sql} NOT NULL DEFAULT ''"
        )

    if "image_blob" not in existing_columns:
        type_sql = "BYTEA" if engine.dialect.name == "postgresql" else "BLOB"
        statements.append(f"ALTER TABLE alumni_profiles ADD COLUMN image_blob {type_sql}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
