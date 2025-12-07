from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.models import init_db
from pydantic import BaseModel,Field,field_validator
import re

from app.config import verify_signature,settings
from app.storage import insert_message,fetch_messages,get_stats
from fastapi import HTTPException,Request
from datetime import datetime,timezone
from fastapi import Query

from fastapi.responses import PlainTextResponse
from app.metrics import inc_http_requests, inc_webhook_result, observe_latency, render_prometheus

from app.logging_utils import new_request_id,utc_now,log_event


#Lifespan for startup and shutdown of the app
@asynccontextmanager
async def lifespan(app:FastAPI):
    db = await init_db(settings.DATABASE_URL)
    app.state.db = db

    yield

    await app.state.db.close()

app = FastAPI(title="Assignment",lifespan=lifespan)

@app.middleware("http")
async def logging_middleware(request:Request,call_next):
    request_id = new_request_id()
    request.state.request_id = request_id

    start = datetime.now(timezone.utc)
    response = await call_next(request)
    latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    log_event({
        "ts":utc_now(),
        "level":"info",
        "request_id":request_id,
        "method":request.method,
        "path":request.url.path,
        "status":response.status_code,
        "latency_ms":round(latency_ms,2)
    })

    return response

#Middleware for tracking latency,status_code and path counts
@app.middleware("http")
async def metrics_middleware(request:Request,call_next):
    import time
    start = time.perf_counter()

    response = await call_next(request)

    latency_ms = (time.perf_counter() - start) * 1000
    observe_latency(latency_ms)

    inc_http_requests(request.url.path,response.status_code)

    return response



class WebHookMessage(BaseModel):
    message_id:str = Field(min_length=1)
    from_:str = Field(alias="from")
    to:str
    ts:str
    text:str | None = Field(default=None,max_length=4096)

    @field_validator("from_","to")
    def validate_msisdn(cls,v):
        if not re.fullmatch(r"\+\d+",v):
            raise ValueError("Must be in E.164 format,start with + and digits only")
        return v

    @field_validator("ts")
    def validate_timestamp(cls,v):
        try:
            if not v.endswith("Z"):
                raise ValueError("timestamp must end with Z")
            datetime.fromisoformat(v.replace("Z","+00:00"))
        except Exception:
            raise ValueError("invalid ISO-8601 UTC timestamp")
        
        return v


# WebHook Endpoint
@app.post("/webhook")
async def webhook(request:Request):
    raw_body = await request.body()
    header_sig = request.headers.get("X-Signature")

    if not verify_signature(settings.WEBHOOK_SECRET,raw_body,header_sig):
        inc_webhook_result("invalid_signature")

        log_event({
            "ts": utc_now(),
            "level": "error",
            "request_id": request.state.request_id,
            "method": "POST",
            "path": "/webhook",
            "status": 401,
            "result": "invalid_signature"
        })

        raise HTTPException(status_code=401,detail="invalid signature")
    
    try:
        data = await request.json()
    except Exception:
        log_event({
            "ts": utc_now(),
            "level": "error",
            "request_id": request.state.request_id,
            "method": "POST",
            "path": "/webhook",
            "status": 422,
            "result": "invalid_json"
        })
        raise HTTPException(status_code=422,detail="invalid JSON")


    try:
        msg = WebHookMessage.model_validate(data)
    except Exception as e:
        
        log_event({
            "ts": utc_now(),
            "level": "error",
            "request_id": request.state.request_id,
            "method": "POST",
            "path": "/webhook",
            "status": 422,
            "result": "validation_error",
        })
        raise HTTPException(status_code=422,detail=str(e))
    
    msg_dict = {
        "message_id":msg.message_id,
        "from_msisdn":msg.from_,
        "to_msisdn":msg.to,
        "ts":msg.ts,
        "text":msg.text,
        "created_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    }

    inserted = await insert_message(request.app.state.db,msg_dict)

    if inserted:
        inc_webhook_result("created")
    else:
        inc_webhook_result("duplicate")

    log_event({
        "ts": utc_now(),
        "level": "info",
        "request_id": request.state.request_id,
        "method": "POST",
        "path": "/webhook",
        "status": 200,
        "message_id": msg.message_id,
        "dup": not inserted,
        "result": "created" if inserted else "duplicate"
    })

    return {"status":"ok"}

#Messages Endpoint
@app.get("/messages")
async def list_messages(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_filter: str | None = Query(None, alias="from"),
    since: str | None = None,
    q: str | None = None,
):
    if since:
        if not since.endswith("Z"):
            raise HTTPException(status_code=422,detail="since must end with Z")
        try:
            datetime.fromisoformat(since.replace("Z","+00:00"))
        except:
            raise HTTPException(status_code=422,detail="invalid since timestamp")
    
    messages,total = await fetch_messages(
        request.app.state.db,
        limit=limit,
        offset=offset,
        from_filter=from_filter,
        since = since,
        q=q
    )

    return {
        "data":messages,
        "total":total,
        "limit":limit,
        "offset":offset
    }


#Stats Endpoint
@app.get("/stats")
async def stats(request:Request):
    return await get_stats(request.app.state.db)
    


#Health Live Endpoint
@app.get('/health/live')
async def health_live():
    return JSONResponse({"status":"alive"})

# Health/Ready Endpoint
@app.get("/health/ready")
async def health_ready(request:Request):
    if not settings.WEBHOOK_SECRET:
        return JSONResponse({
            "status":"error",
            "reason":"WEBHOOK_SECRET not set",
        },
        status_code=503
        )

    try:
        conn = request.app.state.db
        await conn.execute("SELECT 1 FROM messages LIMIT 1;")
    except Exception as e:
        return JSONResponse({
            "status":"error",
            "reason":"database not ready"
        },
        status_code=503
        )
    
    return JSONResponse({"status":"ready"})


# Prometheus Style metrics endpoint 
@app.get("/metrics",response_class=PlainTextResponse)
async def metrics():
    return render_prometheus()