import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
db_file = Path(__file__).resolve().parent / "gst_local.db"
sqlite_url = f"sqlite:///{db_file.as_posix()}"


def _build_engine(url: str | None):
    target_url = url or sqlite_url
    if target_url.startswith("sqlite:///./") or target_url.strip() in (
        "sqlite:///gst_local.db",
        "sqlite:///:memory:",
    ):
        if not target_url.endswith(":memory:"):
            target_url = sqlite_url

    if target_url.startswith("postgresql://"):
        target_url = target_url.replace("postgresql://", "postgresql+psycopg://", 1)

    connect_args = {}
    if target_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    try:
        eng = create_engine(
            target_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            **({"pool_timeout": 3} if not target_url.startswith("sqlite") else {}),
        )
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except Exception as exc:
        if not target_url.startswith("sqlite"):
            logger.warning(
                "Primary database (%s) unreachable: %s. Falling back to local SQLite at %s",
                target_url.split("@")[-1] if "@" in target_url else target_url,
                exc,
                sqlite_url,
            )
            fallback_args = {"check_same_thread": False}
            fallback_eng = create_engine(sqlite_url, connect_args=fallback_args)
            return fallback_eng
        raise exc


engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def run_migrations(target_engine=None):
    """
    Safely and idempotently ensure all tables and columns exist in the database.
    Handles schema migrations for import batches and audit logs without data loss.
    """
    from sqlalchemy import inspect
    from models.base import Base
    import models.models  # ensure all models are registered with Base.metadata

    eng = target_engine or engine
    # 1. Create any missing tables defined in metadata
    Base.metadata.create_all(bind=eng)

    # 2. Check and alter invoices table for added columns if upgrading an existing DB
    try:
        inspector = inspect(eng)
        table_names = inspector.get_table_names()
        if "invoices" in table_names:
            cols = {col["name"] for col in inspector.get_columns("invoices")}
            with eng.begin() as conn:
                if "import_batch_id" not in cols:
                    logger.info("Migrating schema: adding import_batch_id column to invoices table.")
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN import_batch_id VARCHAR(64)"))
                    try:
                        conn.execute(text("CREATE INDEX ix_invoices_import_batch_id ON invoices (import_batch_id)"))
                    except Exception:
                        pass
                if "updated_at" not in cols:
                    logger.info("Migrating schema: adding updated_at column to invoices table.")
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN updated_at DATETIME"))
    except Exception as mig_err:
        logger.warning("Schema migration warning: %s", mig_err)


# Run migrations once on engine initialization
try:
    run_migrations(engine)
except Exception as _init_mig_err:
    logger.warning("Initial database migration warning: %s", _init_mig_err)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


