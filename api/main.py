import time
import logging
import httpx
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from arq import create_pool
from arq.connections import RedisSettings
from shared.schemas import MessageRequest, MessagePriority
from api.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(title="WASocket API")

# Security
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return api_key
redis_pool = None
http_client = None

@app.on_event("startup")
async def startup():
    global redis_pool, http_client
    # Parse redis_url for RedisSettings
    from urllib.parse import urlparse
    logger.info(f"Connecting to Redis using URL: {settings.redis_url}")
    u = urlparse(settings.redis_url)
    redis_settings = RedisSettings(
        host=u.hostname or "localhost",
        port=u.port or 6379,
        password=u.password
    )
    
    redis_pool = await create_pool(redis_settings)
    http_client = httpx.AsyncClient(timeout=5.0)
    logger.info(f"API Started | Connected to Redis at {u.hostname}:{u.port or 6379}")

@app.on_event("shutdown")
async def shutdown():
    if redis_pool:
        await redis_pool.close()
    if http_client:
        await http_client.aclose()

# Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response: Response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"Method: {request.method} Path: {request.url.path} "
        f"Status: {response.status_code} Duration: {duration:.4f}s"
    )
    return response

@app.get("/health")
async def health_check():
    health = {
        "status": "ok",
        "timestamp": time.time(),
        "services": {
            "api": "CONNECTED",
            "engine": "UNKNOWN",
            "worker": "UNKNOWN"
        },
        "queue": {
            "high": 0,
            "default": 0
        }
    }

    # 1. Check Engine
    try:
        resp = await http_client.get(f"{settings.engine_url}/status")
        if resp.status_code == 200:
            engine_data = resp.json()
            health["services"]["engine"] = engine_data.get("status", "CONNECTED")
        else:
            health["services"]["engine"] = "ERROR"
    except Exception:
        health["services"]["engine"] = "DISCONNECTED"

    # 2. Check Worker Heartbeat
    if redis_pool:
        heartbeat = await redis_pool.get("wasocket:worker_heartbeat")
        if heartbeat:
            last_heartbeat = float(heartbeat)
            if time.time() - last_heartbeat < 60:
                health["services"]["worker"] = "CONNECTED"
            else:
                health["services"]["worker"] = "STALE"
        else:
            health["services"]["worker"] = "DISCONNECTED"

        # 3. Queue Size
        health["queue"]["high"] = await redis_pool.zcard("arq:queue:high")
        health["queue"]["default"] = await redis_pool.zcard("arq:queue")

    # Overall Status
    if any(s in ["DISCONNECTED", "ERROR"] for s in health["services"].values()):
        health["status"] = "degraded"
    
    return health

@app.get("/metrics")
async def get_metrics():
    """
    Exposes basic metrics about the queue lengths.
    """
    if not redis_pool:
        return {"error": "Redis not connected"}
    
    # arq uses zsets for queues
    high_queue_len = await redis_pool.zcard("arq:queue:high") if hasattr(redis_pool, 'zcard') else "unknown"
    default_queue_len = await redis_pool.zcard("arq:queue")
    
    return {
        "queue_length": {
            "high": high_queue_len,
            "default": default_queue_len
        },
        "timestamp": time.time()
    }

@app.post("/send", dependencies=[Depends(get_api_key)])
async def send_message(payload: MessageRequest):
    start_enqueue = time.time()
    job = await redis_pool.enqueue_job(
        "send_whatsapp_message",
        phone=payload.phone,
        message=payload.message,
        metadata=payload.metadata,
        priority=payload.priority,
        queued_at=time.time()
    )
    enqueue_duration = time.time() - start_enqueue
    
    return {
        "success": True,
        "job_id": job.job_id,
        "priority": payload.priority,
        "queued_at": time.time(),
        "enqueue_latency_ms": round(enqueue_duration * 1000, 2)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
