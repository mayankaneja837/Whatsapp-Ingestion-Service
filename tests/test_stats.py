from app.config import settings
from .conftest import make_sig


def send(client, mid, ts):
    body = {
        "message_id": mid,
        "from": "+19999999999",
        "to": "+12222222222",
        "ts": ts,
        "text": "hello"
    }
    sig = make_sig(settings.WEBHOOK_SECRET, body)
    client.post("/webhook", json=body, headers={"X-Signature": sig})


def test_stats_basic(client):
    send(client, "s1", "2025-01-01T10:00:00Z")
    send(client, "s2", "2025-01-02T10:00:00Z")

    r = client.get("/stats")
    data = r.json()

    assert data["total_messages"] == 2
    assert data["senders_count"] == 1
    assert data["messages_per_sender"][0]["count"] == 2
    assert data["first_message_ts"] == "2025-01-01T10:00:00Z"
    assert data["last_message_ts"] == "2025-01-02T10:00:00Z"
