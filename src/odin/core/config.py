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
    # Cortesía real (§2.6 de task.md): intervalo mínimo entre dos peticiones
    # EXITOSAS al mismo dominio, sin importar cuántos workers concurrentes
    # haya. Antes solo se usaba como base del backoff en reintentos; ahora
    # también gobierna el throttle de `_DomainThrottle` en scrapers/base.py.
    request_delay: float = float(os.getenv("REQUEST_DELAY", "1.5"))
    fetch_workers: int = int(os.getenv("FETCH_WORKERS", "4"))
    fetch_retries: int = int(os.getenv("FETCH_RETRIES", "3"))
    user_agent: str = os.getenv(
        "USER_AGENT",
        "OdinNewsBot/1.0 (+contacto: jeancarlosazar@gmail.com)",
    )
    # Apagar solo para pruebas locales contra un servidor propio; en producción
    # respetar robots.txt no es opcional.
    respect_robots_txt: bool = _flag("ODIN_RESPECT_ROBOTS_TXT", default=True)

    # --- Motor de análisis (decide el GASTO) ---
    # Se elige SIEMPRE de forma explícita, nunca por la presencia de
    # GEMINI_API_KEY: tener la llave configurada no significa querer pagar por
    # cada análisis (puede estar ahí para el CLI, o simplemente olvidada en el
    # .env). Una credencial no debe ser un interruptor de comportamiento
    # facturable. Ver CLAUDE.md y task.md §3.2.
    # "groq+gemini" es el único valor que puede facturar SIN pedirlo de frente:
    # corre Groq (gratis) y solo cae a Gemini cuando Groq falla — el gasto es la
    # excepción, pero existe. Se elige igual de explícitamente que "gemini".
    analyzer: str = _choice(
        "ODIN_ANALYZER", "local", ("local", "gemini", "groq", "hybrid", "groq+gemini")
    )

    # Cadena de Gemini para el fallback de "groq+gemini" (ver
    # analysis/fallback_analyzer.py). Dos cuentas de Google DISTINTAS —una en el
    # free tier y otra con facturación activada— para que el gasto sea el último
    # recurso: cuando Groq falla, se prueba primero la cuenta gratuita
    # (GEMINI_API_KEY_FREE, no factura pero tiene un límite diario bajo) y solo
    # si esa también se agota, la de pago (GEMINI_API_KEY_PAID). La MISMA key no
    # sirve para ambas: el free tier y la facturación se activan por proyecto de
    # Google, así que son dos credenciales de dos proyectos distintos.
    #
    # Si no se define ninguna de las dos, "groq+gemini" cae a la key única de
    # GEMINI_API_KEY/GOOGLE_API_KEY (comportamiento histórico: un solo Gemini).
    # Se leen aquí y no como flag de gasto porque el gasto ya lo decide
    # ODIN_ANALYZER; estas solo dicen QUÉ credenciales usa esa cadena.
    gemini_api_key_free: str = os.getenv("GEMINI_API_KEY_FREE", "")
    gemini_api_key_paid: str = os.getenv("GEMINI_API_KEY_PAID", "")

    # Árbitro de entidades ambiguas: una llamada EXTRA y facturada a Gemini por
    # cada análisis con personas dudosas, aparte del motor principal. Opt-in
    # explícito, por la misma razón. Solo tiene efecto con ODIN_ANALYZER=local:
    # los motores LLM ya excluyen los nombres que solo bautizan un lugar (ver
    # `arbitrate_ambiguous_persons` en services/analyze_service.py).
    gemini_arbiter: bool = _flag("ODIN_GEMINI_ARBITER", default=False)

    # --- Jobs de POST /api/analyze (services/analyze_service.py) ---
    # Reusar el análisis de una URL ya analizada y NO guardada, si es reciente:
    # analizar dos veces la misma nota es pagar/gastar rate limit dos veces por
    # el mismo resultado. La ventana es corta a propósito — un medio puede
    # editar la nota, y pasado ese rato conviene volver a leerla. 0 lo apaga.
    analyze_reuse_minutes: int = int(os.getenv("ODIN_ANALYZE_REUSE_MINUTES", "60"))
    # Un job que lleva demasiado en `running` ya no va a terminar: o el proceso
    # se reinició a mitad (BackgroundTasks vive en memoria) o la llamada quedó
    # colgada. Se marca como fallido al arrancar en vez de dejar al cliente
    # esperando hasta su propio timeout.
    analyze_job_stale_minutes: int = int(os.getenv("ODIN_ANALYZE_JOB_STALE_MINUTES", "15"))
    # Los jobs terminados guardan el CUERPO COMPLETO del artículo en
    # `result_json`; sin poda la tabla crece sin techo. 0 desactiva el borrado.
    analyze_job_ttl_hours: int = int(os.getenv("ODIN_ANALYZE_JOB_TTL_HOURS", "48"))

    # --- API: descarga de URLs del usuario (anti-SSRF, ver url_guard.py) ---
    # Allowlist de medios. Se aceptan también los subdominios de cada uno.
    # El default cubre los medios que el proyecto ya scrapea (ver
    # `scrapers/SCRAPERS`): si hay un scraper para una fuente, pegar a mano un
    # link suyo en /api/analyze debe funcionar sin configurar nada extra.
    allowed_domains: tuple[str, ...] = _csv(
        "ODIN_ALLOWED_DOMAINS",
        "listindiario.com,diariolibre.com,elnacional.com.do,hoy.com.do,"
        "elcaribe.com.do,almomento.net,eldia.com.do,n.com.do,acento.com.do",
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

    # --- Observabilidad (§7.1 de task.md) ---
    # Sentry es opt-in: sin DSN configurado, sentry_sdk.init nunca se llama.
    sentry_dsn: str = os.getenv("ODIN_SENTRY_DSN", "")
    sentry_environment: str = os.getenv("ODIN_SENTRY_ENVIRONMENT", "development")
    # Formato de logs: "json" en producción (para agregadores), "console"
    # (texto legible con color) para desarrollo local. Ver observability.py.
    log_format: str = _choice("ODIN_LOG_FORMAT", "console", ("json", "console"))
    log_level: str = os.getenv("ODIN_LOG_LEVEL", "INFO").upper()


settings = Settings()
