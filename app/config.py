from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Optional

class Settings(BaseSettings):
    WAHA_BASE_URL: str = "http://localhost:3000"
    WAHA_API_KEY: Optional[str] = None
    INTERNAL_API_KEY: str
    WEBHOOK_SECRET_TOKEN: Optional[str] = None

    # In-memory routing map
    # Loaded from WHATSAPP_ROUTING_JSON env var as a JSON string
    # Example: WHATSAPP_ROUTING_JSON='{"919XXXXXXXXX": "https://project-a.com/webhook"}'
    ROUTING_MAP: Dict[str, str] = {}

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
