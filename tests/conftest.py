import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import init_db
from app.config import settings
import json, hmac, hashlib
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch, event_loop):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")

    async def _setup():
        db = await init_db(settings.DATABASE_URL)
        app.state.db = db
        return db
    
    db = event_loop.run_until_complete(_setup())
    yield
    event_loop.run_until_complete(db.close())


@pytest.fixture
def client():
    return TestClient(app)


def make_sig(secret: str, body: dict):
    raw = json.dumps(body, separators=(",", ":")).encode()
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
