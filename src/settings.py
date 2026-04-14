from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    request_timeout_seconds: int = 25

    # Optional email delivery
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_starttls: bool = True
    email_from: str = ""
    default_email_to: str = ""


def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25")),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_use_starttls=os.getenv("SMTP_USE_STARTTLS", "true").lower() == "true",
        email_from=os.getenv("EMAIL_FROM", ""),
        default_email_to=os.getenv("DEFAULT_EMAIL_TO", ""),
    )
