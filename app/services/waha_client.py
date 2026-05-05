import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class WahaClient:
    def __init__(self):
        self.base_url = settings.WAHA_BASE_URL.rstrip("/")
        self.headers = {
            "x-api-key": settings.WAHA_API_KEY,
            "Content-Type": "application/json"
        }

    async def send_text(self, phone: str, message: str):
        url = f"{self.base_url}/api/sendText"
        payload = {
            "chatId": f"{phone}@c.us",
            "text": message,
            "session": "default"  # Default session name
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers, timeout=5.0)
                response.raise_for_status()
                logger.info(f"Message sent to {phone}: {response.status_code}")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"WAHA API error: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error calling WAHA: {str(e)}")
                raise

waha_client = WahaClient()
