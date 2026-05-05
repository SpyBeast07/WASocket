import httpx
import logging
import asyncio
from app.config import settings

logger = logging.getLogger(__name__)

async def forward_webhook(url: str, payload: dict):
    """
    Async fire-and-forget forwarding of webhook events.
    """
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            # We don't wait long, just fire it.
            response = await client.post(url, json=payload)
            logger.info(f"Forwarded to {url}: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to forward to {url}: {str(e)}")

def get_destination_url(chat_id: str) -> str:
    # Extract phone from chatId (e.g., "919XXXXXXXXX@c.us" -> "919XXXXXXXXX")
    phone = chat_id.split("@")[0]
    
    # Check if we have a route for the phone or the full chatId
    url = settings.ROUTING_MAP.get(phone) or settings.ROUTING_MAP.get(chat_id)
    return url
