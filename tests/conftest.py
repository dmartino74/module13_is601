import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.db import get_db
from app.main import app

# Use in-memory SQLite shared across connections for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # keeps the same in-memory DB for all sessions
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables once for the entire test session."""
    Base.metadata.create_all(bind=engine)
    yield
    # Leave tables in place; they exist only in memory during the session.


@pytest.fixture(scope="function")
def db_session():
    """Provide a fresh SQLAlchemy session and override FastAPI get_db per test."""
    session = TestingSessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            # Closed after each test
            session.close()

    # Override the app's DB dependency for the duration of the test
    app.dependency_overrides[get_db] = override_get_db

    yield session

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session (needed for asyncio plugins)."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
