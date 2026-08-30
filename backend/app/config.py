import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")

    GREEN_API_INSTANCE_ID: str = os.getenv("GREEN_API_INSTANCE_ID", "")
    GREEN_API_TOKEN: str = os.getenv("GREEN_API_TOKEN", "")
    GREEN_API_URL: str = os.getenv("GREEN_API_URL", "https://7107.api.greenapi.com")

    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "noreply@mail.albertabishek.com")

    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")

    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    APP_PASSWORD: str = os.getenv("APP_PASSWORD", "")

    TEST_CUSTOMER_EMAIL: str = os.getenv("TEST_CUSTOMER_EMAIL", "test@example.com")
    TEST_CUSTOMER_PHONE: str = os.getenv("TEST_CUSTOMER_PHONE", "+919999999999")

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    APP_ENV: str = os.getenv("APP_ENV", "development")

    RECOVERY_WINDOW_HOURS: int = 72
    MAX_RECOVERY_ATTEMPTS: int = 5
    ESCALATION_INTERVAL_SECONDS: int = 300
    INVOICE_SCAN_INTERVAL_SECONDS: int = 21600


settings = Settings()
