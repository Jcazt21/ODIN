"""Autenticación de Odin — login contra la tabla `users`, que devuelve un JWT
firmado (HS256).

Antes había un único operador contra credenciales del entorno. Ahora cada
documentalista es una fila de `users`, porque atribuir reportes y medir trabajo por
persona exige que las personas existan.

Las credenciales del entorno siguen usándose, pero solo para SEMBRAR al primer
administrador cuando la tabla está vacía (ver `db/users.seed_operator`):

    ODIN_AUTH_USER            usuario del operador inicial (por defecto "admin")
    ODIN_AUTH_PASSWORD_HASH   hash PBKDF2 generado con scripts/hash_password.py
    ODIN_AUTH_PASSWORD        alternativa en claro (solo desarrollo)
    ODIN_JWT_SECRET           clave para firmar los tokens
    ODIN_JWT_TTL_HOURS        vigencia del token (por defecto 12)

Sin contraseña configurada no se siembra nada y nadie puede entrar: el sistema
queda cerrado por defecto en vez de abierto.

El token es sin estado: `require_auth` solo valida firma y vigencia, no
consulta la BD, así que dar de baja a alguien no le revoca el acceso hasta
que el JWT expire (ver el docstring de `require_auth` para el detalle y la
mitigación).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from odin.core.config import settings

if TYPE_CHECKING:
    from odin.db.models import User

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
    """Compara en tiempo constante contra un hash del formato de arriba.

    Un hash que no se puede leer avisa en el log antes de devolver `False`. Sin
    ese aviso es idéntico a una contraseña equivocada, y una fila mal sembrada
    deja al usuario fuera con el mismo 401 de siempre: pasó con un hash cuyos
    `$` llegaron duplicados desde el `.env`, y no había nada que lo delatara.
    """
    try:
        scheme, iterations, salt_b64, digest_b64 = stored.split("$")
        if scheme != _HASH_SCHEME:
            log.warning(
                "hash almacenado con esquema desconocido (%r); se rechaza el acceso",
                scheme[:32],
            )
            return False
        expected = _b64d(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), _b64d(salt_b64), int(iterations)
        )
    except (ValueError, TypeError):
        # A propósito sin el hash ni la contraseña en el mensaje: el log no es
        # lugar para material sensible, y la forma ya dice qué revisar.
        log.warning(
            "hash almacenado ilegible (%d segmentos separados por '$', se esperan 4); "
            "no es una contraseña equivocada sino una fila mal sembrada",
            len(stored.split("$")),
        )
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


def create_token(subject: str, *, must_change_password: bool = False) -> tuple[str, int]:
    """Devuelve (token, segundos_de_vigencia).

    `must_change_password` viaja como claim y no se consulta a la BD en cada
    request: `require_auth` es deliberadamente sin estado (ver su docstring), y
    meterle una query por llamada para leer una bandera contradiría esa
    decisión. El precio es que apagar el portón exige emitir un token nuevo, y
    eso es exactamente lo que hace `change_password`.
    """
    ttl = timedelta(hours=settings.jwt_ttl_hours)
    now = datetime.now(UTC)
    payload = {"sub": subject, "iat": now, "exp": now + ttl}
    if must_change_password:
        payload["mcp"] = True
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
    """Exige un Bearer token válido. Devuelve el usuario (claim `sub`).

    Valida la FIRMA y la vigencia del token, nada más: no consulta la tabla
    `users`. La consecuencia hay que tenerla presente — dar de baja a alguien
    (`is_active=False`) le cierra el login, pero NO invalida el token que ya
    tenga en el navegador: seguirá entrando a los endpoints protegidos solo
    con esta dependencia hasta que el JWT expire (`ODIN_JWT_TTL_HOURS`, 12h
    por defecto). Es el precio de un token sin estado, y es deliberado:
    revalidar contra la BD en cada request obligaría a que todo usuario del
    token exista, y hay flujos que dependen de lo contrario (un artículo
    guardado por alguien ya borrado se conserva, solo pierde la atribución).
    Para cortar el acceso antes, baja `ODIN_JWT_TTL_HOURS`.
    `require_admin` sí revalida, porque el rol sí tiene que poder retirarse
    en el acto.
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = _decode(creds.credentials)
    # Portón del PIN de primer acceso. Vive acá y no en cada router para que no
    # haya forma de olvidarlo en un endpoint nuevo, y en la API y no solo en la
    # pantalla porque una llamada directa esquivaría un portón de frontend.
    # `PASSWORD_CHANGE_REQUIRED` en el detalle: el frontend lo distingue de un
    # 403 por rol y sabe que tiene que ir a la pantalla de cambio.
    if claims.get("mcp"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PASSWORD_CHANGE_REQUIRED",
        )
    return claims.get("sub", "")


def require_auth_allowing_password_change(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Como `require_auth` pero sin el portón. Solo para las dos rutas que el
    usuario TIENE que poder alcanzar con el portón encendido: consultar su
    estado y cambiar la contraseña. Sin esto el portón se cerraría sobre sí
    mismo y nadie podría salir de él."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode(creds.credentials).get("sub", "")


def require_admin(username: str = Depends(require_auth)) -> str:
    """Exige que el usuario del token tenga rol `admin`.

    El rol se lee de la BD en cada request y no del token: así, quitarle el rol
    a alguien surte efecto de inmediato en vez de esperar a que su JWT venza.
    """
    import odin.db.users as user_store
    from odin.api import deps

    session = deps.get_session()
    try:
        user = user_store.get_by_username(session, username)
        if user is None or not user.is_active or user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requiere rol de administrador.",
            )
        return username
    finally:
        session.close()


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
    # Enciende la pantalla de cambio obligatorio. Se lee de la BD y no del
    # token para que la interfaz vea el estado real aunque tenga un token viejo.
    must_change_password: bool = False
    # El rol viaja aquí y no en el token: leerlo de la BD en cada arranque de la
    # aplicación hace que quitarle el rol a alguien surta efecto sin esperar a
    # que su JWT venza.
    role: str | None = None


# Hash de descarte con el mismo coste que uno real. Se verifica contra él
# cuando el usuario no existe, para que "usuario inexistente" y "contraseña
# incorrecta" tarden lo mismo y el login no sea un oráculo de qué cuentas hay.
_DUMMY_HASH = hash_password("contraseña-que-nadie-usa")


def authenticate(username: str, password: str) -> User | None:
    """Devuelve el usuario si las credenciales son válidas y está activo."""
    # Import local: `db.users` importa de este módulo (hash_password), así que
    # importarlo arriba cerraría el ciclo.
    import odin.db.users as user_store
    from odin.api import deps

    session = deps.get_session()
    try:
        user = user_store.get_by_username(session, username)
        stored = user.password_hash if user else _DUMMY_HASH
        password_ok = verify_password(password, stored)

        if not user or not password_ok or not user.is_active:
            return None
        # PIN de primer acceso ya consumido: vale una sola vez, y reusarlo se
        # rechaza igual que una contraseña equivocada — decir "ese PIN ya se
        # usó" le confirmaría a un atacante que acertó los 4 dígitos.
        if user.must_change_password and user.temp_password_used_at is not None:
            return None
        if user.must_change_password:
            user.temp_password_used_at = datetime.now(UTC)
            session.commit()
        # Se desprende de la sesión para poder leer sus atributos después de
        # cerrarla (el sessionmaker del proyecto usa expire_on_commit=False,
        # pero expunge lo hace explícito y no depende de esa configuración).
        session.expunge(user)
        return user
    finally:
        session.close()


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request):
    """Entrega un JWT si las credenciales coinciden con una fila de `users`."""
    ip = request.client.host if request.client else "desconocido"

    if _recent_failures(ip) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Espera unos minutos.",
        )

    user = authenticate(req.username.strip(), req.password)
    if user is None:
        _record_failure(ip)
        log.warning("login fallido para '%s' desde %s", req.username, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )

    _failures.pop(ip, None)
    token, expires_in = create_token(
        user.username, must_change_password=user.must_change_password
    )
    log.info("login correcto de '%s' desde %s", user.username, ip)
    return TokenResponse(access_token=token, expires_in=expires_in, username=user.username)


@router.get("/me", response_model=MeResponse)
def me(username: str = Depends(require_auth_allowing_password_change)):
    """Valida el token guardado en el navegador al abrir la aplicación, y
    devuelve el rol para que la interfaz sepa qué mostrar."""
    import odin.db.users as user_store
    from odin.api import deps

    session = deps.get_session()
    try:
        user = user_store.get_by_username(session, username)
        return MeResponse(
            username=username,
            role=user.role if user else None,
            must_change_password=bool(user and user.must_change_password),
        )
    finally:
        session.close()


MIN_PASSWORD_LENGTH = 8


class ChangePasswordRequest(BaseModel):
    new_password: str


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    req: ChangePasswordRequest,
    username: str = Depends(require_auth_allowing_password_change),
):
    """Reemplaza la contraseña y devuelve un token nuevo.

    Emitir token nuevo no es opcional: el portón viaja como claim, así que el
    token con el que se llega aquí seguiría cerrando todo lo demás.

    No pide la contraseña actual porque quien llega con el portón encendido
    acaba de probarla al entrar, y el PIN ya se consumió.
    """
    import odin.db.users as user_store
    from odin.api import deps

    new_password = req.new_password
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.",
        )

    session = deps.get_session()
    try:
        user = user_store.get_by_username(session, username)
        if user is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        # Reponer el PIN dejaría viva justo la credencial que se quiere retirar.
        if verify_password(new_password, user.password_hash):
            raise HTTPException(
                status_code=422,
                detail="La contraseña nueva no puede ser la misma que ya tenías.",
            )

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.temp_password_used_at = None
        session.commit()
        log.info("contraseña cambiada por '%s'", username)
        token, expires_in = create_token(user.username)
        return TokenResponse(access_token=token, expires_in=expires_in, username=user.username)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("password_change_failed")
        raise HTTPException(status_code=500, detail="Error interno cambiando la contraseña.") from None
    finally:
        session.close()
