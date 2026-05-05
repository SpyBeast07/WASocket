from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Optional

class Settings(BaseSettings):
    WAHA_BASE_URL: str = "http://localhost:3000"
    WAHA_API_KEY: Optional[str] = None
    INTERNAL_API_KEY: str

    # In-memory routing map loaded from WHATSAPP_ROUTING_JSON env var
    # Example: WHATSAPP_ROUTING_JSON='{"919XXXXXXXXX": "https://project.com/webhook"}'
    ROUTING_MAP: Dict[str, str] = {}

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="")

settings = Settings()
