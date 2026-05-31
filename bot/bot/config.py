from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str
    telegram_bot_username: str = "OkederBot"
    backend_api_url: str = "http://localhost:8000/v1"
    bot_webhook_url: str = ""
    bot_webhook_secret: str = ""
    telegram_use_polling: bool = True
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "development"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


settings = BotSettings()
