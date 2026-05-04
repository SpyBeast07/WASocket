import time
import logging
from fastapi import FastAPI, Request, Response
from arq import create_pool
from arq.connections import RedisSettings
from shared.schemas import MessageRequest
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
    # Parse redis_url or use default RedisSettings
    # For now, we'll use a direct DSN if supported by your arq version or default
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

@app.post("/send")
async def send_message(payload: MessageRequest):
    # Push task to Redis
    # The task name 'send_whatsapp_message' will be handled by the worker in Phase 3
    job = await redis_pool.enqueue_job(
        "send_whatsapp_message",
        phone=payload.phone,
        message=payload.message,
        metadata=payload.metadata
    )
    
    return {
        "success": True,
        "job_id": job.job_id,
        "queued_at": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
