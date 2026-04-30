from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NovelNest API"
    api_prefix: str = "/api/v1"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    database_url: str = "sqlite:///./novelnest.db"
    redis_url: str = "redis://localhost:6379/0"
    web_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
