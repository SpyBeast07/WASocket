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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("worker")

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
        # Pacing for stability
        await asyncio.sleep(random.uniform(1.0, 2.0))
    
    # 3. Execution (Persistent Connection)
    try:
        start_engine_call = time.time()
        response = await client.post(
            f"{settings.engine_url}/send-message",
            json={"phone": phone, "message": message},
            timeout=10.0 # Low timeout for stability
        )
        engine_duration = time.time() - start_engine_call
        
        # OPTIMIZED: Accept 200 (Blocking) or 202 (Fire-and-Forget)
        if response.status_code in [200, 202]:
            total_latency = time.time() - (queued_at or time.time())
            pickup_delay = start_pickup - (queued_at or start_pickup)
            
            logger.info(
                f"[Job {job_id}] SENT | Phone: {phone} | Priority: {priority} | "
                f"Latency: {total_latency:.2f}s (Pickup: {pickup_delay:.2f}s, Engine: {engine_duration:.2f}s)"
            )
            return response.json()
        else:
            logger.error(f"[Job {job_id}] ENGINE ERROR {response.status_code}: {response.text}")
            raise Retry(defer=retry_count * 2)

    except (httpx.RequestError, Retry) as exc:
        if isinstance(exc, Retry):
            raise exc
        logger.error(f"[Job {job_id}] TRANSPORT ERROR: {exc}")
        raise Retry(defer=5)

async def startup(ctx):
    # STEP 1: Persistent Connection Pooling
    ctx['http_client'] = httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
    )
    logger.info("High-Performance Worker Started | HTTP Connection Pooling Active")

async def shutdown(ctx):
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
    redis_settings = RedisSettings()
    queues = ('arq:queue:high', 'arq:queue')
    max_jobs = 1 # Keep sequential for single-session stability
    job_timeout = 30
    max_retries = 3
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
