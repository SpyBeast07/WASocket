from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Optional

class Settings(BaseSettings):
    WAHA_BASE_URL: str = "http://localhost:3000"
    WAHA_API_KEY: Optional[str] = None
    INTERNAL_API_KEY: str
    WEBHOOK_SECRET_TOKEN: Optional[str] = None

    # In-memory routing map
    # Example: {"919XXXXXXXXX": "https://project-a.com/webhook"}
    # ROUTING_MAP: Dict[str, str] = {}
    ROUTING_MAP: Dict[str, str] = {
        "919269972395": "https://localhost:8000/api/whatsapp-webhook",
        "120363023456789": "https://your-project-b.com/group-handler"
    }

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
