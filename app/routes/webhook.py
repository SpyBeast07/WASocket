from fastapi import APIRouter, BackgroundTasks, Request, Header, HTTPException
import logging
from app.config import settings
from app.services.router import forward_webhook

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def handle_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_waha_token: str = Header(None, alias="x-waha-token")
):
    # Optional: Validate secret token if configured
    if settings.WAHA_WEBHOOK_SECRET and x_waha_token != settings.WAHA_WEBHOOK_SECRET:
        logger.warning("Unauthorized webhook attempt with invalid token")
        raise HTTPException(status_code=401, detail="Invalid secret token")
    # WAHA sends event in body
    try:
        payload = await request.json()
    except Exception:
        logger.error("Invalid JSON received in webhook")
        return {"status": "error", "message": "Invalid JSON"}

    # Extract event data
    event_type = payload.get("event")
    data = payload.get("payload", {})

    # Log incoming event
    logger.info(f"Received WAHA event: {event_type}")

    # If it's a message event, check if it's from me
    if event_type == "message":
        from_me = data.get("fromMe", False)
        if from_me:
            logger.debug("Ignoring message from self")
            return {"status": "ignored", "reason": "fromMe"}

    # Add forwarding to background tasks (non-blocking)
    background_tasks.add_task(forward_webhook, data)

    return {"status": "received"}
