import asyncio
import logging
from fastapi import APIRouter, Request, BackgroundTasks, Header, Query, Optional
from app.config import settings
from app.services.router import forward_webhook, get_destination_url

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def handle_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    # Optional secret validation if configured
    if settings.WEBHOOK_SECRET_TOKEN:
        if x_api_key != settings.WEBHOOK_SECRET_TOKEN and token != settings.WEBHOOK_SECRET_TOKEN:
            logger.warning("Unauthorized webhook attempt")
            return {"status": "unauthorized"}

    payload = await request.json()
    event_type = payload.get("event")
    
    # We only care about message events for now (WAHA events like 'message', 'message.upsert', etc.)
    # Adjust based on WAHA version/config
    data = payload.get("payload", {})
    
    # Ignore if message from me
    if data.get("fromMe"):
        return {"status": "ignored", "reason": "fromMe"}

    chat_id = data.get("chatId") or data.get("from")
    if not chat_id:
        return {"status": "ignored", "reason": "no_chat_id"}

    logger.info(f"Received webhook event: {event_type} from {chat_id}")

    # Routing
    dest_url = get_destination_url(chat_id)
    if dest_url:
        logger.info(f"Routing event to {dest_url}")
        background_tasks.add_task(forward_webhook, dest_url, payload)
    else:
        logger.debug(f"No route found for {chat_id}")

    return {"status": "received"}
