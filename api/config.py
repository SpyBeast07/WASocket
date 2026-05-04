from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379"
    engine_url: str = "http://engine:3000"
    api_port: int = 8000
    api_key: str = "wasocket-secret-key"
    debug: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
