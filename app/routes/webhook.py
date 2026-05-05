import logging
from fastapi import APIRouter, Request, BackgroundTasks
from app.config import settings
from app.services.router import forward_webhook, get_destination_url

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    # 1. Parse payload
    payload = await request.json()
    event_type = payload.get("event")
    data = payload.get("payload", {})
    chat_id = data.get("chatId") or data.get("from")
    
    # 2. LOG EVERYTHING (Critical for debugging)
    logger.info(f"--- WEBHOOK RECEIVED ---")
    logger.info(f"Event: {event_type}")
    logger.info(f"From: {chat_id}")
    logger.info(f"fromMe: {data.get('fromMe')}")
    
    # 3. Ignore if message from me (loop prevention)
    if data.get("fromMe"):
        logger.info(f"Action: IGNORED (reason: fromMe)")
        return {"status": "ignored", "reason": "fromMe"}

    if not chat_id:
        logger.warning(f"Action: IGNORED (reason: no chat_id found in payload)")
        return {"status": "ignored", "reason": "no_chat_id"}

    # 4. Routing
    dest_url = get_destination_url(chat_id)
    if dest_url:
        logger.info(f"Action: ROUTING to {dest_url}")
        background_tasks.add_task(forward_webhook, dest_url, payload)
    else:
        logger.info(f"Action: NO ROUTE FOUND for {chat_id}")

    return {"status": "received"}
