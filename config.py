"""Configuración central del proyecto Odin.

Lee variables desde el entorno / archivo .env con valores por defecto sensatos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://odin:odin@localhost:5432/odin",
    )
    max_articles_per_source: int = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "25"))
    request_delay: float = float(os.getenv("REQUEST_DELAY", "1.5"))
    fetch_workers: int = int(os.getenv("FETCH_WORKERS", "4"))
    fetch_retries: int = int(os.getenv("FETCH_RETRIES", "3"))
    user_agent: str = os.getenv(
        "USER_AGENT",
        "OdinNewsBot/1.0 (+contacto: jeancarlosazar@gmail.com)",
    )


settings = Settings()
