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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
