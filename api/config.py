from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    POSTGRES_USER: str = "ce_user"
    POSTGRES_PASSWORD: str = "devpassword"
    POSTGRES_DB: str = "contentengine"
    POSTGRES_PORT: int = 5433
    POSTGRES_HOST: str = "localhost"

    # JWT Security Settings
    JWT_SECRET_KEY: str = "super-secret-jwt-key-replace-in-prod"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
