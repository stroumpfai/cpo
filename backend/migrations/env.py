import os
import sys

from alembic import context
from sqlalchemy import create_engine

# Make backend modules importable regardless of the working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schema  # noqa: E402

target_metadata = schema.metadata


def _database_url() -> str:
    url = context.config.get_main_option("sqlalchemy.url")
    if url:
        return url
    import config as app_config

    return f"sqlite:///{app_config.DATABASE_PATH}"


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
