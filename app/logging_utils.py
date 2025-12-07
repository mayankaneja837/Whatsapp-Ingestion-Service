import json
import uuid
from datetime import datetime,timezone

def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def new_request_id():
    return str(uuid.uuid4())

def log_event(data:dict):
    try:
        print(json.dumps(data,separators=(",",":")))
    except Exception:
        print('{"level":"error","msg":"failed to serialize log"}')