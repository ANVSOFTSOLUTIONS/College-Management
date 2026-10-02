from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "School Management API"
    api_prefix: str = "/api/v1"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3307
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "school_management"
    cors_origins: str = "http://localhost:5173"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 60

    # Fernet key for secrets stored in the database (a school's Cashfree secret key).
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    data_encryption_key: str = ""

    # Backups: where they go (default ~/school_backups), the mysqldump program, and the
    # secret the daily cron job sends to /internal/backups/run (unset = cron trigger off).
    backup_dir: str = ""
    mysqldump_path: str = "mysqldump"
    backup_token: str = ""

    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 60

    # Parent SMS alerts. Off until the school has an SMS provider account; while
    # off, alerts are still recorded (status "not_sent") but nothing is sent.
    sms_enabled: bool = False
    sms_provider: str = "msg91"
    sms_msg91_auth_key: str = ""
    sms_msg91_template_absence: str = ""
    sms_msg91_template_remark: str = ""
    sms_msg91_template_fee: str = ""
    sms_msg91_template_result: str = ""
    # WhatsApp through MSG91, alongside SMS. Templates are the approved WhatsApp template names.
    whatsapp_enabled: bool = False
    whatsapp_msg91_number: str = ""  # the MSG91 integrated WhatsApp number, e.g. 919876543210
    whatsapp_language: str = "en"
    whatsapp_template_absence: str = ""
    whatsapp_template_remark: str = ""
    whatsapp_template_fee: str = ""
    whatsapp_template_result: str = ""

    # Outgoing email (demo requests from the landing page). Off until SMTP_HOST is set.
    # Port 587 uses STARTTLS; set SMTP_USE_SSL=true for port 465.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_use_ssl: bool = False
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    # Who gets an email for every demo request (comma-separated).
    demo_request_emails: str = "support@anvsoftsolutions.com,sales@anvsoftsolutions.com"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
