from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Bella Italia Voice Agent"
    RESTAURANT_NAME: str = "Bella Italia"
    LOG_LEVEL: str = "INFO"

    # Gemini
    GEMINI_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://restaurant_user:restaurant_pass@localhost:5432/restaurant_voice"

    # Square (optional — stub for now)
    SQUARE_ACCESS_TOKEN: Optional[str] = None
    SQUARE_LOCATION_ID: Optional[str] = None

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
