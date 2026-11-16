import os
from collections.abc import Generator

import pytest
from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import app
from app.modules.auth.model import User
from app.modules.auth.security import hash_password
from app.modules.customers import model as _customer_model  # noqa: F401
from app.modules.organizations import model as _organization_model  # noqa: F401
from app.modules.roles import model as _roles_model  # noqa: F401
from app.modules.roles.model import Role
from app.modules.roles.service import seed_default_rbac
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

settings = get_settings()
settings.jwt_secret_key = "test-only-secret-key-that-is-long-enough"
settings.access_token_expire_minutes = 15
settings.refresh_token_expire_days = 7
settings.login_max_attempts = 5
settings.login_window_seconds = 900
settings.login_lockout_seconds = 900

test_database_url = os.getenv("TEST_DATABASE_URL", "sqlite://")
is_sqlite_test_database = test_database_url.startswith("sqlite")
test_engine = create_engine(
    test_database_url,
    connect_args={"check_same_thread": False} if is_sqlite_test_database else {},
    poolclass=StaticPool if is_sqlite_test_database else None,
)

if is_sqlite_test_database:

    @event.listens_for(test_engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    if is_sqlite_test_database:
        with test_engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
            Base.metadata.drop_all(connection)
            connection.commit()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
            Base.metadata.create_all(connection)
            connection.commit()
    else:
        Base.metadata.drop_all(test_engine)
        Base.metadata.create_all(test_engine)
    with TestingSessionLocal() as session:
        seed_default_rbac(session)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_session_factory():
    return TestingSessionLocal


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user(db_session: Session) -> User:
    record = User(
        id="11111111-1111-1111-1111-111111111111",
        username="alice",
        email="alice@example.com",
        password_hash=hash_password("CorrectPassword123!"),
        display_name="Alice",
        status="active",
        roles=[db_session.scalar(select(Role).where(Role.code == "employee"))],
    )
    db_session.add(record)
    db_session.commit()
    return record
