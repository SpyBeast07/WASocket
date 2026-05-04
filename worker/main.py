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

# Rate Limit Config (Messages Per Minute)
RATE_LIMIT_MPM = 60
RATE_LIMIT_KEY = "wasocket:rate_limit"

async def check_rate_limit(redis):
    """
    Sliding window rate limiter using Redis.
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
    Optimized task to send a WhatsApp message with priority handling and rate limiting.
    """
    job_id = ctx.get('job_id')
    retry_count = ctx.get('job_try', 1)
    redis = ctx['redis']
    
    if not await check_rate_limit(redis):
        logger.warning(f"[Job {job_id}] RATE LIMIT REACHED. Deferring...")
        raise Retry(defer=10)

    if priority == MessagePriority.HIGH:
        delay = random.uniform(0.5, 1.5)
    else:
        delay = random.uniform(2, 5)
    
    await asyncio.sleep(delay)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.engine_url}/send-message",
                json={"phone": phone, "message": message},
                timeout=30.0
            )
            if response.status_code == 200:
                result = response.json()
                latency = time.time() - (queued_at or time.time())
                logger.info(f"[Job {job_id}] SUCCESS: {phone} (Priority: {priority}, Latency: {latency:.2f}s)")
                return result
            else:
                logger.warning(f"[Job {job_id}] RETRYING: Engine returned {response.status_code}")
                raise Retry(defer=retry_count * 5)
        except (httpx.RequestError, Retry) as exc:
            if isinstance(exc, Retry):
                raise exc
            logger.error(f"[Job {job_id}] ERROR: Connection failed: {exc}")
            raise Retry(defer=retry_count * 5)

async def on_job_failure(ctx, exc):
    job_id = ctx.get('job_id')
    redis = ctx['redis']
    job_data = {
        "job_id": job_id,
        "error": str(exc),
        "args": ctx.get('job_args'),
        "kwargs": ctx.get('job_kwargs'),
        "failed_at": time.time()
    }
    await redis.lpush("wasocket:dlq", json.dumps(job_data))
    logger.error(f"[Job {job_id}] FAILED PERMANENTLY: Moved to DLQ.")

async def startup(ctx):
    logger.info("High-Performance Worker Started. Monitoring queues: high, default")

async def shutdown(ctx):
    logger.info("High-Performance Worker Shutting Down...")

class WorkerSettings:
    functions = [send_whatsapp_message]
    redis_settings = RedisSettings()
    
    # We'll use the default queue for all messages to ensure reliability
    # Priority (delays) is handled inside the task logic
    queue_name = 'arq:queue'
    
    max_jobs = 1
    job_timeout = 60
    max_retries = 3
    on_startup = startup
    on_shutdown = shutdown
    on_job_error = on_job_failure

if __name__ == "__main__":
    from arq import run_worker
    # Required for Python 3.10+
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        run_worker(WorkerSettings)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
