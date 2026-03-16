# Whatsapp-Ingestion-Service

A FastAPI-based webhook service for receiving, storing, and querying SMS messages with HMAC signature verification, pagination, and Prometheus-style metrics.

## Table of Contents

- [Prerequisites](#prerequisites)
- [How to Run](#how-to-run)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [How to Hit Endpoints](#how-to-hit-endpoints)
- [Design Decisions](#design-decisions)
- [Testing](#testing)
- [Project Structure](#project-structure)

## Prerequisites

- Docker and Docker Compose
- Make (optional, for convenience commands)

## How to Run

### Using Make (Recommended)

```bash
# Start the service
make up

# View logs
make logs

# Stop the service
make down

# Run tests
make test
```

### Using Docker Compose Directly

```bash
# Start the service
docker compose up -d --build

# View logs
docker compose logs -f api

# Stop the service
docker compose down -v
```

### Manual Setup

1. Create a `.env` file in the project root:
```bash
DATABASE_URL=sqlite:///data/messages.db
WEBHOOK_SECRET=your-secret-key-here
LOG_LEVEL=INFO
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### URLs

Once the service is running, it will be available at:

- **API Base URL**: `http://localhost:8000`
- **API Documentation**: `http://localhost:8000/docs` (Swagger UI)
- **Alternative Docs**: `http://localhost:8000/redoc` (ReDoc)

## Environment Variables

Create a `.env` file in the project root with the following variables:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | SQLite database URL (must start with `sqlite:///`) | Yes | - |
| `WEBHOOK_SECRET` | Secret key for HMAC signature verification | Yes | - |
| `LOG_LEVEL` | Logging level | No | `INFO` |

Example `.env` file:
```
DATABASE_URL=sqlite:///data/messages.db
WEBHOOK_SECRET=my-secret-key-12345
LOG_LEVEL=INFO
```

## API Endpoints

### 1. POST `/webhook`

Receives and stores incoming SMS messages with HMAC signature verification.

**Headers:**
- `X-Signature`: HMAC-SHA256 signature of the request body (required)

**Request Body:**
```json
{
  "message_id": "msg-123",
  "from": "+1234567890",
  "to": "+0987654321",
  "ts": "2025-01-10T10:00:00Z",
  "text": "Hello, world!"
}
```

**Field Validations:**
- `message_id`: Required, minimum length 1
- `from`: Required, must be E.164 format (starts with `+` followed by digits)
- `to`: Required, must be E.164 format
- `ts`: Required, ISO-8601 UTC timestamp ending with `Z`
- `text`: Optional, maximum length 4096 characters

**Response:**
- `200 OK`: Message stored successfully
  ```json
  {"status": "ok"}
  ```
- `401 Unauthorized`: Invalid signature
- `422 Unprocessable Entity`: Validation error or invalid JSON

**Behavior:**
- Duplicate `message_id` values are handled idempotently (returns success without error)
- All requests are logged with request ID, timestamp, and result

### 2. GET `/messages`

Retrieves paginated list of messages with optional filtering.

**Query Parameters:**
- `limit` (int): Number of messages per page (1-100, default: 50)
- `offset` (int): Number of messages to skip (default: 0)
- `from` (string, optional): Filter by sender MSISDN (E.164 format)
- `since` (string, optional): Filter messages after this timestamp (ISO-8601 UTC, must end with `Z`)
- `q` (string, optional): Search query for message text (case-insensitive partial match)

**Response:**
```json
{
  "data": [
    {
      "message_id": "msg-123",
      "from": "+1234567890",
      "to": "+0987654321",
      "ts": "2025-01-10T10:00:00Z",
      "text": "Hello, world!",
      "created_at": "2025-01-10T10:00:00Z"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

**Sorting:**
- Messages are sorted by `ts` (ascending), then by `message_id` (ascending)

### 3. GET `/stats`

Returns aggregate statistics about stored messages.

**Response:**
```json
{
  "total_messages": 150,
  "senders_count": 25,
  "messages_per_sender": [
    {"from": "+1234567890", "count": 15},
    {"from": "+0987654321", "count": 12}
  ],
  "first_message_ts": "2025-01-01T00:00:00Z",
  "last_message_ts": "2025-01-10T23:59:59Z"
}
```

**Fields:**
- `total_messages`: Total count of all messages
- `senders_count`: Number of unique senders
- `messages_per_sender`: Top 10 senders by message count (descending)
- `first_message_ts`: Timestamp of the earliest message
- `last_message_ts`: Timestamp of the most recent message

### 4. GET `/health/live`

Liveness probe endpoint.

**Response:**
```json
{"status": "alive"}
```

### 5. GET `/health/ready`

Readiness probe endpoint. Checks if the service is ready to accept traffic.

**Response:**
- `200 OK`: Service is ready
  ```json
  {"status": "ready"}
  ```
- `503 Service Unavailable`: Service not ready (missing WEBHOOK_SECRET or database unavailable)
  ```json
  {"status": "error", "reason": "..."}
  ```

### 6. GET `/metrics`

Returns Prometheus-style metrics in plain text format.

**Response:**
```
http_requests_total{path="/webhook",status="200"} 150
http_requests_total{path="/messages",status="200"} 45
webhook_requests_total{result="created"} 140
webhook_requests_total{result="duplicate"} 10
webhook_requests_total{result="invalid_signature"} 5
request_latency_ms_bucket{le="100"} 120
request_latency_ms_bucket{le="500"} 180
request_latency_ms_bucket{le="+Inf"} 195
request_latency_ms_count 195
```

## How to Hit Endpoints

### Using cURL

#### 1. Send a Webhook Message

```bash
# First, compute the HMAC signature
SECRET="your-secret-key"
BODY='{"message_id":"msg-123","from":"+1234567890","to":"+0987654321","ts":"2025-01-10T10:00:00Z","text":"Hello"}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

# Send the request
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -d "$BODY"
```

#### 2. List Messages

```bash
# Get first page
curl "http://localhost:8000/messages?limit=10&offset=0"

# Filter by sender
curl "http://localhost:8000/messages?from=%2B1234567890"

# Filter by date
curl "http://localhost:8000/messages?since=2025-01-01T00:00:00Z"

# Search text
curl "http://localhost:8000/messages?q=hello"

# Combined filters
curl "http://localhost:8000/messages?from=%2B1234567890&since=2025-01-01T00:00:00Z&q=hello&limit=20"
```

#### 3. Get Statistics

```bash
curl http://localhost:8000/stats
```

#### 4. Check Health

```bash
# Liveness
curl http://localhost:8000/health/live

# Readiness
curl http://localhost:8000/health/ready
```

#### 5. Get Metrics

```bash
curl http://localhost:8000/metrics
```

### Using Python

```python
import requests
import hmac
import hashlib
import json

BASE_URL = "http://localhost:8000"
SECRET = "your-secret-key"

# Send webhook message
body = {
    "message_id": "msg-123",
    "from": "+1234567890",
    "to": "+0987654321",
    "ts": "2025-01-10T10:00:00Z",
    "text": "Hello, world!"
}

# Compute signature
raw_body = json.dumps(body, separators=(",", ":")).encode()
signature = hmac.new(
    SECRET.encode(),
    raw_body,
    hashlib.sha256
).hexdigest()

# Send request
response = requests.post(
    f"{BASE_URL}/webhook",
    json=body,
    headers={"X-Signature": signature}
)
print(response.json())

# List messages
response = requests.get(
    f"{BASE_URL}/messages",
    params={"limit": 10, "offset": 0, "from": "+1234567890"}
)
print(response.json())

# Get stats
response = requests.get(f"{BASE_URL}/stats")
print(response.json())
```

### Using the Interactive API Documentation

1. Start the service: `make up`
2. Open your browser: `http://localhost:8000/docs`
3. Use the Swagger UI to test endpoints interactively

## Design Decisions

### HMAC Verification Implementation

**Location**: `app/config.py`

The HMAC signature verification is implemented using Python's built-in `hmac` and `hashlib` modules:

1. **Algorithm**: HMAC-SHA256
2. **Signature Computation**:
   ```python
   computed = hmac.new(
       key=secret.encode("utf-8"),
       msg=raw_body,
       digestmod=hashlib.sha256
   ).hexdigest()
   ```

3. **Verification**:
   - Uses `hmac.compare_digest()` for constant-time comparison to prevent timing attacks
   - Compares the computed signature with the `X-Signature` header value
   - Returns `False` if secret or signature header is missing

4. **Security Considerations**:
   - The raw request body (bytes) is used for signature computation, ensuring exact match
   - Constant-time comparison prevents timing-based attacks
   - Signature must be provided in the `X-Signature` header

5. **Error Handling**:
   - Invalid signatures return `401 Unauthorized`
   - Missing signatures are treated as invalid
   - All signature verification failures are logged and tracked in metrics

### Pagination Contract

**Location**: `app/storage.py` and `app/main.py`

The pagination system follows a standard offset-based approach:

1. **Parameters**:
   - `limit`: Number of items per page (1-100, default: 50)
   - `offset`: Number of items to skip (default: 0)

2. **Response Structure**:
   ```json
   {
     "data": [...],      // Array of message objects
     "total": 100,       // Total count matching filters (before pagination)
     "limit": 50,        // Requested limit
     "offset": 0         // Requested offset
   }
   ```

3. **Implementation Details**:
   - Two separate queries: one for data, one for total count
   - Total count query excludes `limit` and `offset` parameters
   - Consistent sorting: `ORDER BY ts ASC, message_id ASC` ensures deterministic pagination
   - Filters (from, since, q) are applied to both data and count queries

4. **Filtering**:
   - `from`: Exact match on `from_msisdn` column
   - `since`: Timestamp comparison (`ts >= since`)
   - `q`: Case-insensitive partial text match using `LIKE` with wildcards

5. **Edge Cases**:
   - Empty results return `{"data": [], "total": 0, ...}`
   - Offset beyond total returns empty data array with correct total
   - Filters can be combined (AND logic)

### `/stats` and Metrics Implementation

#### `/stats` Endpoint

**Location**: `app/storage.py`

The `/stats` endpoint provides aggregate statistics:

1. **Metrics Collected**:
   - `total_messages`: Count of all messages
   - `senders_count`: Count of distinct senders
   - `messages_per_sender`: Top 10 senders by message count
   - `first_message_ts`: Earliest message timestamp
   - `last_message_ts`: Most recent message timestamp

2. **Implementation**:
   - Uses separate SQL queries for each metric
   - Top senders query uses `GROUP BY` and `ORDER BY count DESC LIMIT 10`
   - Timestamps use `ORDER BY ts` with `LIMIT 1` for min/max

3. **Performance**:
   - Each metric is a separate query (could be optimized with a single query if needed)
   - No caching (always returns current data)

#### Prometheus Metrics (`/metrics`)

**Location**: `app/metrics.py`

The metrics system tracks:

1. **HTTP Request Metrics**:
   - `http_requests_total{path, status}`: Counter of HTTP requests by path and status code
   - Tracked in middleware for all requests

2. **Webhook Metrics**:
   - `webhook_requests_total{result}`: Counter of webhook results
   - Values: `created`, `duplicate`, `invalid_signature`

3. **Latency Metrics**:
   - `request_latency_ms_bucket{le}`: Histogram buckets for request latency
   - Buckets: `100ms`, `500ms`, `+Inf`
   - `request_latency_ms_count`: Total number of requests

4. **Implementation**:
   - In-memory storage (resets on restart)
   - Thread-safe operations (Python GIL handles this for single-threaded async)
   - Prometheus-compatible format (plain text)

5. **Middleware Integration**:
   - `metrics_middleware`: Tracks all HTTP requests, latency, and status codes
   - `logging_middleware`: Logs all requests in JSON format to stdout

## Testing

Run the test suite:

```bash
# Using Make
make test

# Using pytest directly
pytest tests/ -v

# Run specific test file
pytest tests/test_webhook.py -v
```

The test suite includes:
- Webhook signature verification tests
- Message insertion and duplicate handling
- Pagination and filtering tests
- Statistics endpoint tests

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application and endpoints
│   ├── config.py            # Settings and HMAC verification
│   ├── models.py            # Database models and initialization
│   ├── storage.py           # Database operations (CRUD, stats)
│   ├── metrics.py           # Prometheus metrics collection
│   └── logging_utils.py     # Logging utilities
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_webhook.py      # Webhook endpoint tests
│   ├── test_messages.py    # Messages endpoint tests
│   └── test_stats.py       # Stats endpoint tests
├── data/                    # Database storage directory
├── Dockerfile              # Container definition
├── docker-compose.yaml    # Docker Compose configuration
├── Makefile               # Convenience commands
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## License

This project is part of a coding assignment.

