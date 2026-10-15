import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Auto-secure cookies when APP_URL is https or SESSION_COOKIE_SECURE=1
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
        or (os.environ.get("APP_URL") or "").startswith("https://")
    )
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # Turso / Database
    TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "")
    TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
    USE_LOCAL_DB = os.environ.get("USE_LOCAL_DB", "0") == "1" or not (
        TURSO_DATABASE_URL and TURSO_AUTH_TOKEN
    )

    # Cloudinary (required on Vercel – no persistent local disk)
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

    # App
    APP_URL = os.environ.get("APP_URL", "http://localhost:5000")
    TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kathmandu")
    CURRENCY = "NPR"
    CURRENCY_SYMBOL = "Rs."

    # Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # Pagination
    ITEMS_PER_PAGE = 20

    # Order polling interval (seconds) for tracking
    ORDER_POLL_INTERVAL = 5

    # Email (SMTP) – optional; notifications skipped if not set
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT") or 587)
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    # Admin alert address for new orders / reservations
    ADMIN_NOTIFY_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL", "")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
