from app.config import settings
from .conftest import make_sig


def insert(client, mid, text="hello", ts="2025-01-10T10:00:00Z"):
    body = {
        "message_id": mid,
        "from": "+11111111111",
        "to": "+12222222222",
        "ts": ts,
        "text": text
    }
    sig = make_sig(settings.WEBHOOK_SECRET, body)
    client.post("/webhook", json=body, headers={"X-Signature": sig})


def test_messages_pagination(client):
    for i in range(5):
        insert(client, f"m{i}")

    r = client.get("/messages?limit=2&offset=0")
    data = r.json()
    assert r.status_code == 200
    assert len(data["data"]) == 2
    assert data["total"] == 5


def test_messages_filter_from(client):
    insert(client, "fx1")

    r = client.get("/messages", params={"from": "+11111111111"})
    assert r.status_code == 200
    assert len(r.json()["data"]) >= 1


def test_messages_filter_since(client):
    insert(client, "old1", ts="2025-01-01T10:00:00Z")
    insert(client, "new1", ts="2025-01-20T10:00:00Z")

    r = client.get("/messages?since=2025-01-10T00:00:00Z")
    ids = [m["message_id"] for m in r.json()["data"]]

    assert "new1" in ids
    assert "old1" not in ids


def test_messages_search_q(client):
    insert(client, "msg1", text="hello world")
    insert(client, "msg2", text="bye")

    r = client.get("/messages?q=hello")
    data = r.json()["data"]

    assert len(data) == 1
    assert data[0]["text"] == "hello world"
