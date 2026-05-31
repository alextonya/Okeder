from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    api_base_url: str = "http://localhost:8000"
    pwa_base_url: str = "http://localhost:3000"

    # Database
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # Clerk
    clerk_secret_key: str = ""
    clerk_webhook_secret: str = ""
    clerk_jwks_url: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_platform_fee_pct: float = 0.05

    # Eventbrite
    eventbrite_private_token: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_bot_username: str = "OkederBot"  # à configurer avec le vrai @username

    # WhatsApp
    whatsapp_api_url: str = "https://graph.facebook.com/v18.0"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Foursquare Places API (gratuit, 1000 req/jour)
    foursquare_api_key: str = ""

    # Email notifications (B)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@okeder.app"

    # Push notifications VAPID (C)
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_claims_email: str = "mailto:contact@okeder.app"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


settings = Settings()
