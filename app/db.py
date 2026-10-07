import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agros.db")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}
    if os.getenv("DATABASE_POOLER_MODE") == "transaction":
        # Supavisor/PgBouncer transaction pooling can switch backend sessions.
        # Disable psycopg automatic prepared statements for safe serverless use.
        connect_args["prepare_threshold"] = None

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_recycle=int(os.getenv("DATABASE_POOL_RECYCLE_SECONDS", "300")),
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

@contextmanager
def db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def init_db():
    from app import commos_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
