# api/config.py

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    POSTGRES_USER: str = Field(default="")
    POSTGRES_PASSWORD: str = Field(default="")
    POSTGRES_DB: str = Field(default="")
    POSTGRES_PORT: int = 5433
    POSTGRES_HOST: str = "localhost"

    # Redis Settings
    REDIS_PORT: int = 6380
    REDIS_HOST: str = "localhost"

    # Qdrant Settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # AI/LLM Settings
    OPENAI_API_KEY: SecretStr = Field(default=SecretStr(""))

    # JWT Security Settings
    # Providing empty string as fallback so Pylance doesn't complain about missing arguments during instantiation
    JWT_SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = "HS256"

    # 24 hours is a security risk. Reduced to 30 mins (Enterprise Standard)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 240

    # CORS Settings
    FRONTEND_URLS: str = Field(
        default="http://localhost:3000,https://alliases.duckdns.org"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [url.strip() for url in self.FRONTEND_URLS.split(",") if url.strip()]

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Pylance is now happy because all required fields have valid defaults in code
# However, Pydantic will still correctly override them with your .env variables
settings = Settings()
