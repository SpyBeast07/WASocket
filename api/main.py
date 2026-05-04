import time
import logging
from fastapi import FastAPI, Request, Response
from arq import create_pool
from arq.connections import RedisSettings
from shared.schemas import MessageRequest, MessagePriority
from api.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(title="WASocket API")

# Redis pool for arq
redis_pool = None

@app.on_event("startup")
async def startup():
    global redis_pool
    # Use default RedisSettings
    redis_pool = await create_pool(RedisSettings())
    logger.info("Connected to Redis for task queueing")

@app.on_event("shutdown")
async def shutdown():
    if redis_pool:
        await redis_pool.close()

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
    return {
        "status": "ok",
        "service": "api",
        "redis_connected": redis_pool is not None
    }

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

@app.post("/send")
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
