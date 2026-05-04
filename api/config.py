from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    engine_url: str = "http://localhost:3000"
    api_port: int = 8000
    debug: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
