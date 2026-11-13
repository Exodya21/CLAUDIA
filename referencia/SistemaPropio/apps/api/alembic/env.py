from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app import (  # noqa: F401  (registra las tablas)
    models,
    models_comm,
    models_agents,
    models_bank,
    models_reception,
    models_economy,
    models_accounting,
    models_hr,
    models_immigration,
    models_security,
    models_work,
)
from app.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def _url() -> str:
    # Prioridad: variable de entorno; si no existe, la configuración de la app (lee apps/api/.env).
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    from app.config import get_settings

    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
