from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from app.modules.auth import model as _auth_model  # noqa: F401
from app.modules.customers import model as _customer_model  # noqa: F401
from app.modules.organizations import model as _organization_model  # noqa: F401
from app.modules.roles import model as _roles_model  # noqa: F401
from sqlalchemy import engine_from_config, pool

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    if context.dialect.name == "sqlite" and {
        type(inspected_type).__name__,
        type(metadata_type).__name__,
    } <= {
        "JSON",
        "JSONB",
    }:
        return False
    return None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_type,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
