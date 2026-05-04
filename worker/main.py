import random
import asyncio
import httpx
import logging
import json
import time
from arq.connections import RedisSettings
from arq.worker import Retry
from api.config import settings
from shared.schemas import MessagePriority
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("worker")

# Parse redis_url for WorkerSettings
logger.info(f"Worker connecting to Redis using URL: {settings.redis_url}")
u = urlparse(settings.redis_url)
worker_redis_settings = RedisSettings(
    host=u.hostname or "localhost",
    port=u.port or 6379,
    password=u.password
)

# Rate Limit Config
RATE_LIMIT_MPM = 60
RATE_LIMIT_KEY = "wasocket:rate_limit"

async def check_rate_limit(redis):
    """
    Sliding window rate limiter using Redis.
    Allows for small bursts while maintaining a 60 MPM average.
    """
    current_time = int(time.time())
    window_start = current_time - 60
    await redis.zremrangebyscore(RATE_LIMIT_KEY, 0, window_start)
    count = await redis.zcard(RATE_LIMIT_KEY)
    if count >= RATE_LIMIT_MPM:
        return False
    await redis.zadd(RATE_LIMIT_KEY, {str(time.time()): current_time})
    return True

async def worker_heartbeat(redis):
    """
    Updates a heartbeat key in Redis to signal worker health.
    """
    while True:
        try:
            await redis.setex("wasocket:worker_heartbeat", 60, str(time.time()))
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            await asyncio.sleep(10)

async def send_whatsapp_message(ctx, phone: str, message: str, priority: str = "default", metadata: dict = None, queued_at: float = None):
    """
    AUDITED: Low-latency execution pipeline.
    """
    start_pickup = time.time()
    job_id = ctx.get('job_id')
    retry_count = ctx.get('job_try', 1)
    redis = ctx['redis']
    client = ctx['http_client'] # Reusing persistent client

    # 1. Rate Limiting (Smart)
    if not await check_rate_limit(redis):
        logger.warning(f"[Job {job_id}] Rate limit (60 MPM) hit. Deferring...")
        raise Retry(defer=5)

    # 2. Optimized Delay (0 for High, minimal for Default)
    if priority == MessagePriority.HIGH:
        pass # Zero artificial delay for High Priority
    else:
        # Reduced pacing for better throughput
        await asyncio.sleep(random.uniform(0.2, 0.5))
    
    # 3. Execution (Persistent Connection)
    try:
        start_engine_call = time.time()
        response = await client.post(
            f"{settings.engine_url}/send-message",
            json={"phone": phone, "message": message},
            timeout=10.0
        )
        response.raise_for_status()
        engine_duration = time.time() - start_engine_call
        
        total_latency = time.time() - (queued_at or time.time())
        pickup_delay = start_pickup - (queued_at or start_pickup)
        
        logger.info(
            f"[Job {job_id}] DISPATCHED | Phone: {phone} | Priority: {priority} | "
            f"Latency: {total_latency:.2f}s (Pickup: {pickup_delay:.2f}s, Engine: {engine_duration:.2f}s)"
        )
        return response.json()

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        error_text = exc.response.text
        
        # PERMANENT ERRORS (Don't retry)
        if status_code == 400:
            logger.error(f"[Job {job_id}] PERMANENT ERROR {status_code}: {error_text}")
            return {"success": False, "error": error_text, "permanent": True}
        
        # TEMPORARY ERRORS (Retry)
        logger.warning(f"[Job {job_id}] TEMPORARY ENGINE ERROR {status_code}. Retrying...")
        raise Retry(defer=retry_count * 2)

    except (httpx.RequestError, asyncio.TimeoutError) as exc:
        logger.warning(f"[Job {job_id}] TRANSPORT ERROR: {exc}. Retrying...")
        raise Retry(defer=5)
    
    except Retry as exc:
        raise exc
    
    except Exception as exc:
        logger.error(f"[Job {job_id}] UNEXPECTED ERROR: {exc}")
        # Let on_job_failure handle it
        raise exc

async def startup(ctx):
    # STEP 1: Persistent Connection Pooling
    ctx['http_client'] = httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
    )
    
    # STEP 2: Heartbeat Task
    ctx['heartbeat_task'] = asyncio.create_task(worker_heartbeat(ctx['redis']))
    
    logger.info("High-Performance Worker Started | Heartbeat Active")

async def shutdown(ctx):
    if 'heartbeat_task' in ctx:
        ctx['heartbeat_task'].cancel()
    await ctx['http_client'].aclose()
    logger.info("Worker Gracefully Shut Down")

async def on_job_failure(ctx, exc):
    job_id = ctx.get('job_id')
    redis = ctx['redis']
    job_data = {
        "job_id": job_id, "error": str(exc),
        "args": ctx.get('job_args'), "failed_at": time.time()
    }
    await redis.lpush("wasocket:dlq", json.dumps(job_data))
    logger.error(f"[Job {job_id}] PERMANENT FAILURE -> DLQ")

class WorkerSettings:
    functions = [send_whatsapp_message]
    redis_settings = worker_redis_settings
    queues = ('arq:queue:high', 'arq:queue')
    max_jobs = 1 # Keep sequential for single-session stability
    job_timeout = 30
    max_retries = 10 # Allow more retries during engine restarts
    on_startup = startup
    on_shutdown = shutdown
    on_job_error = on_job_failure

if __name__ == "__main__":
    from arq import run_worker
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        run_worker(WorkerSettings)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
