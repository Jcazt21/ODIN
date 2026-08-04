"""Configuración central del proyecto Odin.

Lee variables desde el entorno / archivo .env con valores por defecto sensatos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _csv(name: str, default: str) -> tuple[str, ...]:
    """Lee una lista separada por comas del entorno."""
    return tuple(v.strip() for v in os.getenv(name, default).split(",") if v.strip())


def _choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    """Lee un valor del entorno restringido a un conjunto cerrado.

    Falla al arrancar en vez de caer a un default silencioso: si alguien escribe
    `ODIN_ANALYZER=gemeni`, mejor un error claro que correr meses con el motor
    equivocado sin enterarse.
    """
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        raise ValueError(
            f"{name}={value!r} no es un valor válido. Opciones: {', '.join(allowed)}."
        )
    return value


_TRUE = frozenset({"1", "true", "t", "yes", "y", "on", "si", "sí"})
_FALSE = frozenset({"0", "false", "f", "no", "n", "off", ""})


def _flag(name: str, default: bool = False) -> bool:
    """Lee un booleano del entorno. Un valor irreconocible es un error, no un
    `False` silencioso — importa cuando el flag habilita gasto."""
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{name}={raw!r} no es un booleano válido (usa 1/0, true/false).")


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

    # --- Motor de análisis (decide el GASTO) ---
    # Se elige SIEMPRE de forma explícita, nunca por la presencia de
    # GEMINI_API_KEY: tener la llave configurada no significa querer pagar por
    # cada análisis (puede estar ahí para el CLI, o simplemente olvidada en el
    # .env). Una credencial no debe ser un interruptor de comportamiento
    # facturable. Ver CLAUDE.md y task.md §3.2.
    analyzer: str = _choice("ODIN_ANALYZER", "local", ("local", "gemini", "groq", "hybrid"))

    # Árbitro de entidades ambiguas: una llamada EXTRA y facturada a Gemini por
    # cada análisis con personas dudosas, aparte del motor principal. Opt-in
    # explícito, por la misma razón.
    gemini_arbiter: bool = _flag("ODIN_GEMINI_ARBITER", default=False)

    # --- API: descarga de URLs del usuario (anti-SSRF, ver url_guard.py) ---
    # Allowlist de medios. Se aceptan también los subdominios de cada uno.
    allowed_domains: tuple[str, ...] = _csv(
        "ODIN_ALLOWED_DOMAINS",
        "listindiario.com,diariolibre.com,elnacional.com.do,hoy.com.do,"
        "elcaribe.com.do,almomento.net,eldia.com.do,n.com.do",
    )
    max_url_length: int = int(os.getenv("ODIN_MAX_URL_LENGTH", "2048"))
    max_download_bytes: int = int(os.getenv("ODIN_MAX_DOWNLOAD_BYTES", str(5 * 1024 * 1024)))
    max_redirects: int = int(os.getenv("ODIN_MAX_REDIRECTS", "3"))
    fetch_timeout: int = int(os.getenv("ODIN_FETCH_TIMEOUT", "20"))

    # --- API: autenticación y CORS ---
    # Usuario único; no hay registro. Ver auth.py.
    auth_username: str = os.getenv("ODIN_AUTH_USER", "admin")
    auth_password_hash: str = os.getenv("ODIN_AUTH_PASSWORD_HASH", "")
    auth_password: str = os.getenv("ODIN_AUTH_PASSWORD", "")  # solo desarrollo
    jwt_secret: str = os.getenv("ODIN_JWT_SECRET", "")
    jwt_ttl_hours: int = int(os.getenv("ODIN_JWT_TTL_HOURS", "12"))
    # Orígenes permitidos por CORS. En dev es el servidor de Vite; en Docker el
    # frontend habla por nginx (mismo origen) y esto no llega a usarse.
    cors_origins: tuple[str, ...] = _csv(
        "ODIN_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    )


settings = Settings()
