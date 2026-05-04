import random
import asyncio
import httpx
import logging
import json
from arq.connections import RedisSettings
from arq.worker import Retry
from api.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("worker")

async def send_whatsapp_message(ctx, phone: str, message: str, metadata: dict = None):
    """
    Task to send a WhatsApp message with retries and randomized delays.
    """
    job_id = ctx.get('job_id')
    # Get current retry count
    retry_count = ctx.get('job_try', 1)
    
    logger.info(f"[Job {job_id}] Attempt {retry_count} for {phone}")
    
    # 1. Randomized delay (2-5 seconds) to prevent overloading WhatsApp
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
                logger.info(f"[Job {job_id}] SUCCESS: Message sent to {phone}")
                return result
            else:
                logger.warning(f"[Job {job_id}] RETRYING: Engine returned {response.status_code}")
                # Raise Retry exception for arq to handle backoff
                raise Retry(defer=retry_count * 5) # Exponential-ish backoff
                
        except (httpx.RequestError, Retry) as exc:
            if isinstance(exc, Retry):
                raise exc
            
            logger.error(f"[Job {job_id}] ERROR: Connection failed: {exc}")
            raise Retry(defer=retry_count * 5)

async def on_job_failure(ctx, exc):
    """
    Moves failed jobs to a Dead-Letter Queue (DLQ) in Redis.
    """
    job_id = ctx.get('job_id')
    # Use the redis connection from context
    redis = ctx['redis']
    
    job_data = {
        "job_id": job_id,
        "error": str(exc),
        "args": ctx.get('job_args'),
        "kwargs": ctx.get('job_kwargs')
    }
    
    # Push to a simple Redis list as DLQ
    await redis.lpush("wasocket:dlq", json.dumps(job_data))
    logger.error(f"[Job {job_id}] FAILED PERMANENTLY: Moved to DLQ. Error: {exc}")

class WorkerSettings:
    """
    Arq Worker configuration.
    """
    functions = [send_whatsapp_message]
    redis_settings = RedisSettings() # Default localhost:6379
    
    # Requirements
    max_jobs = 1               # Ensure sequential processing to avoid WhatsApp bans
    job_timeout = 60           # 1 minute timeout per job
    max_retries = 3            # Retry max 3 times
    
    # Hooks
    @staticmethod
    async def on_startup(ctx):
        logger.info("Worker Bridge Started. Listening for jobs...")

    @staticmethod
    async def on_shutdown(ctx):
        logger.info("Worker Bridge Shutting Down...")
        
    on_job_error = on_job_failure # Catch all errors and move to DLQ

if __name__ == "__main__":
    from arq import run_worker
    # Explicitly create and set the event loop for Python 3.14 compatibility
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        run_worker(WorkerSettings)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
