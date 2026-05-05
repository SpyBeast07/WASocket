import httpx
import logging
import asyncio
from typing import Dict

logger = logging.getLogger(__name__)

# In-memory routing map
# Key: chat_id (phone number or group id)
# Value: destination webhook URL
ROUTING_MAP: Dict[str, str] = {
    "919XXXXXXXXX": "https://project-a.com/webhook",
    # Add more routes as needed
}

async def forward_webhook(payload: dict):
    # Extract chat_id from WAHA event
    # WAHA message payload typically has payload['chatId'] or payload['from']
    chat_id = payload.get("chatId") or payload.get("from")
    if not chat_id:
        logger.warning("No chat_id found in webhook payload")
        return

    # Normalize chat_id (strip @c.us if present for matching)
    clean_id = chat_id.split("@")[0]
    
    destination_url = ROUTING_MAP.get(clean_id) or ROUTING_MAP.get(chat_id)
    
    if not destination_url:
        logger.debug(f"No route found for chat_id: {chat_id}")
        return

    logger.info(f"Forwarding webhook for {chat_id} to {destination_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Fire and forget with short timeout
            await client.post(destination_url, json=payload, timeout=2.0)
            logger.info(f"Successfully forwarded to {destination_url}")
        except Exception as e:
            logger.error(f"Failed to forward webhook to {destination_url}: {str(e)}")

def get_routing_map():
    return ROUTING_MAP
