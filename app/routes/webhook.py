import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Request, BackgroundTasks, Header, Query
from app.config import settings
from app.services.router import forward_webhook, get_destination_url

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def handle_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    token: Optional[str] = Query(None)
):
    payload = await request.json()
    event_type = payload.get("event")
    data = payload.get("payload", {})
    chat_id = data.get("chatId") or data.get("from")
    
    # LOG EVERYTHING IMMEDIATELY
    logger.info(f"Incoming WAHA Webhook: {event_type} from {chat_id}")
    logger.debug(f"Webhook Auth Check - Header: {x_api_key}, Token: {token}")

    # 1. Optional secret validation if configured
    if settings.WEBHOOK_SECRET_TOKEN:
        if x_api_key != settings.WEBHOOK_SECRET_TOKEN and token != settings.WEBHOOK_SECRET_TOKEN:
            logger.warning(f"Unauthorized webhook attempt from {chat_id}")
            return {"status": "unauthorized"}

    # 2. Ignore if message from me (loop prevention)
    if data.get("fromMe"):
        logger.info(f"Ignored event from {chat_id} (reason: fromMe)")
        return {"status": "ignored", "reason": "fromMe"}

    if not chat_id:
        return {"status": "ignored", "reason": "no_chat_id"}

    # 3. Routing
    dest_url = get_destination_url(chat_id)
    if dest_url:
        logger.info(f"Routing event from {chat_id} to {dest_url}")
        background_tasks.add_task(forward_webhook, dest_url, payload)
    else:
        logger.debug(f"No route found for {chat_id}")

    return {"status": "received"}
