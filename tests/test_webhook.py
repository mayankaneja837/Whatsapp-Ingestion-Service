from app.config import settings
from .conftest import make_sig


def test_webhook_valid_insert(client):
    body = {
        "message_id": "m1",
        "from": "+11111111111",
        "to": "+12222222222",
        "ts": "2025-01-10T10:00:00Z",
        "text": "Hello"
    }

    sig = make_sig(settings.WEBHOOK_SECRET, body)

    r = client.post("/webhook", json=body, headers={"X-Signature": sig})
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_webhook_duplicate(client):
    body = {
        "message_id": "m2",
        "from": "+11111111111",
        "to": "+12222222222",
        "ts": "2025-01-10T10:00:00Z",
        "text": "Hi"
    }
    sig = make_sig(settings.WEBHOOK_SECRET, body)

    r1 = client.post("/webhook", json=body, headers={"X-Signature": sig})
    r2 = client.post("/webhook", json=body, headers={"X-Signature": sig})

    assert r1.status_code == 200
    assert r2.status_code == 200  # idempotent


def test_webhook_invalid_signature(client):
    body = {
        "message_id": "m3",
        "from": "+11111111111",
        "to": "+12222222222",
        "ts": "2025-01-10T10:00:00Z",
        "text": "Bad sig"
    }

    r = client.post("/webhook", json=body, headers={"X-Signature": "wrong"})
    assert r.status_code == 401
