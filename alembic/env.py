from logging.config import fileConfig
import os

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url
from alembic import context

from app.db.base import Base
import app.db.models  # noqa: F401 - ensures models are registered

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ------------------------------------------------------------------
# 🔒 HARD POSTGRES CONFIG (ENV REQUIRED, FAIL CLOSED)
# ------------------------------------------------------------------

def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    if not database_url.lower().startswith("postgresql"):
        raise RuntimeError("DATABASE_URL must start with 'postgresql'")

    config.set_main_option("sqlalchemy.url", database_url)

    try:
        display_url = make_url(database_url).render_as_string(hide_password=True)
    except Exception:
        display_url = database_url

    print(f"Alembic using database URL: {display_url}")
    return database_url


DATABASE_URL = get_database_url()

# ------------------------------------------------------------------
# OFFLINE
# ------------------------------------------------------------------

def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# ------------------------------------------------------------------
# ONLINE
# ------------------------------------------------------------------

def run_migrations_online() -> None:
    connectable = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

# ------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()