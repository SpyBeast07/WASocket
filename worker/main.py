import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

async def main():
    logger.info("Worker started (placeholder)")
    while True:
        await asyncio.sleep(10)
        logger.info("Worker heartbeat")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
