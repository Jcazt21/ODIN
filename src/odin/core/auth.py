"""Autenticación de Odin — login de un solo usuario contra credenciales del
entorno, que devuelve un JWT firmado (HS256).

No hay registro ni tabla de usuarios: es una herramienta interna con un único
operador. Las credenciales viven en el entorno:

    ODIN_AUTH_USER            usuario (por defecto "admin")
    ODIN_AUTH_PASSWORD_HASH   hash PBKDF2 generado con scripts/hash_password.py
    ODIN_AUTH_PASSWORD        alternativa en claro (solo desarrollo)
    ODIN_JWT_SECRET           clave para firmar los tokens
    ODIN_JWT_TTL_HOURS        vigencia del token (por defecto 12)

Si no hay contraseña configurada, el login rechaza todo: el sistema queda
cerrado por defecto en vez de abierto.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from odin.core.config import settings

log = logging.getLogger("odin.auth")

# ── Hash de contraseñas ───────────────────────────────────────────────────────
# PBKDF2-HMAC-SHA256 de la stdlib: sin dependencias nuevas y suficiente para un
# único secreto que ya vive en el entorno. Formato almacenado:
#   pbkdf2_sha256$<iteraciones>$<salt_b64>$<hash_b64>

_HASH_SCHEME = "pbkdf2_sha256"
_ITERATIONS = 600_000


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(plain: str, *, iterations: int = _ITERATIONS) -> str:
    """Devuelve el hash almacenable de una contraseña en claro."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"{_HASH_SCHEME}${iterations}${_b64e(salt)}${_b64e(digest)}"


def verify_password(plain: str, stored: str) -> bool:
    """Compara en tiempo constante contra un hash del formato de arriba."""
    try:
        scheme, iterations, salt_b64, digest_b64 = stored.split("$")
        if scheme != _HASH_SCHEME:
            return False
        expected = _b64d(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), _b64d(salt_b64), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# ── Firma de tokens ───────────────────────────────────────────────────────────

_ALGORITHM = "HS256"

# Sin ODIN_JWT_SECRET se genera uno efímero: la API sigue siendo segura, pero
# los tokens mueren con el proceso (cada reinicio obliga a volver a entrar).
# Preferimos eso a una clave por defecto conocida y publicada en el repo.
if settings.jwt_secret:
    _SECRET = settings.jwt_secret
else:
    _SECRET = secrets.token_urlsafe(48)
    log.warning(
        "ODIN_JWT_SECRET no está configurada: se usará una clave efímera. "
        "Las sesiones se invalidarán al reiniciar la API."
    )

if not (settings.auth_password_hash or settings.auth_password):
    log.warning(
        "Ni ODIN_AUTH_PASSWORD_HASH ni ODIN_AUTH_PASSWORD están configuradas: "
        "el login rechazará cualquier intento y las escrituras quedarán cerradas."
    )
elif settings.auth_password and not settings.auth_password_hash:
    log.warning(
        "Usando ODIN_AUTH_PASSWORD en claro. Para producción genera un hash con "
        "`python scripts/hash_password.py` y configúralo en ODIN_AUTH_PASSWORD_HASH."
    )


def create_token(subject: str) -> tuple[str, int]:
    """Devuelve (token, segundos_de_vigencia)."""
    ttl = timedelta(hours=settings.jwt_ttl_hours)
    now = datetime.now(UTC)
    payload = {"sub": subject, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM), int(ttl.total_seconds())


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión expiró. Vuelve a iniciar sesión.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


# ── Dependencia de FastAPI ────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Exige un Bearer token válido. Devuelve el usuario (claim `sub`)."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode(creds.credentials).get("sub", "")


# ── Freno de fuerza bruta ─────────────────────────────────────────────────────
# En memoria y por proceso: no es rate limiting de verdad (eso es §12 #20), solo
# evita que el login sea un oráculo de contraseñas a velocidad de red.

_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300
_failures: dict[str, list[float]] = {}


def _recent_failures(ip: str) -> int:
    cutoff = time.monotonic() - _WINDOW_SECONDS
    hits = [t for t in _failures.get(ip, []) if t > cutoff]
    if hits:
        _failures[ip] = hits
    else:
        _failures.pop(ip, None)
    return len(hits)


def _record_failure(ip: str) -> None:
    _failures.setdefault(ip, []).append(time.monotonic())


# ── Endpoints ─────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str


class MeResponse(BaseModel):
    username: str


def _credentials_ok(username: str, password: str) -> bool:
    """Compara usuario y contraseña sin cortocircuitar: aunque el usuario no
    coincida, igual verificamos la contraseña para no filtrar por tiempo cuál
    de los dos campos estaba mal."""
    user_ok = hmac.compare_digest(username, settings.auth_username)

    if settings.auth_password_hash:
        pass_ok = verify_password(password, settings.auth_password_hash)
    elif settings.auth_password:
        pass_ok = hmac.compare_digest(password, settings.auth_password)
    else:
        pass_ok = False

    return user_ok and pass_ok


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request):
    """Entrega un JWT si las credenciales coinciden con las del entorno."""
    ip = request.client.host if request.client else "desconocido"

    if _recent_failures(ip) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Espera unos minutos.",
        )

    if not _credentials_ok(req.username.strip(), req.password):
        _record_failure(ip)
        log.warning("login fallido para '%s' desde %s", req.username, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )

    _failures.pop(ip, None)
    token, expires_in = create_token(settings.auth_username)
    log.info("login correcto de '%s' desde %s", settings.auth_username, ip)
    return TokenResponse(
        access_token=token, expires_in=expires_in, username=settings.auth_username
    )


@router.get("/me", response_model=MeResponse)
def me(username: str = Depends(require_auth)):
    """Valida el token guardado en el navegador al abrir la aplicación."""
    return MeResponse(username=username)
