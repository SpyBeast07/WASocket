from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    WAHA_BASE_URL: str = "http://localhost:3000"
    WAHA_API_KEY: str = "your_waha_key"
    INTERNAL_API_KEY: str = "your_secure_key"
    WAHA_WEBHOOK_SECRET: str = "" # Optional secret token for incoming webhooks

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
