"""Lógica de negocio del catálogo de documentalistas."""
from __future__ import annotations

import secrets
import unicodedata

from fastapi import HTTPException
from sqlalchemy import func, select

import odin.db.users as user_store
from odin.api import deps
from odin.api.deps import log
from odin.api.schemas import (
    DOCUMENTALIST_ROLE_VALUES,
    DocumentalistCreated,
    DocumentalistPayload,
    DocumentalistResponse,
    DocumentalistUpdatePayload,
)
from odin.core.auth import hash_password
from odin.db.models import User


def _check_role(role: str) -> None:
    if role not in DOCUMENTALIST_ROLE_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"Rol inválido: '{role}'. Válidos: {', '.join(DOCUMENTALIST_ROLE_VALUES)}.",
        )


def list_documentalists(include_inactive: bool = True) -> list[DocumentalistResponse]:
    session = deps.get_session()
    try:
        stmt = select(User)
        if not include_inactive:
            stmt = stmt.where(User.is_active.is_(True))
        rows = session.scalars(stmt.order_by(User.display_name)).all()
        return [DocumentalistResponse.model_validate(r) for r in rows]
    finally:
        session.close()


def _ascii_letters(value: str) -> str:
    """Deja solo letras a-z, sin acentos ni ñ, en minúsculas.

    NFKD separa la letra de su tilde y el filtro de combinantes descarta la
    tilde; la ñ se traduce aparte porque su descomposición es n + tilde y ese
    es justamente el resultado que se busca. Sin esto, un `username` con acento
    obligaría a teclearlo para entrar — y acá "Núñez" y "Yván" son nombres
    corrientes, no casos raros.
    """
    plain = unicodedata.normalize("NFKD", value)
    return "".join(c for c in plain if c.isascii() and c.isalpha()).lower()


def username_from_name(first_name: str, last_name: str) -> str:
    """Inicial del nombre + 4 primeras letras del apellido: "Yvan Mercado" -> "ymerc".

    Del nombre se usa solo el primero ("Ana María" -> "a"). El apellido se toma
    entero, espacios incluidos: "De la Cruz" es UN apellido y sus 4 primeras
    letras son "dela".

    Un apellido más corto que 4 rinde un usuario más corto, y está bien: es
    igual de único que cualquier otro, y los choques los resuelve quien llama.
    """
    first = _ascii_letters(first_name.strip().split(" ")[0] if first_name.strip() else "")
    last = _ascii_letters(last_name)
    if not first or not last:
        raise ValueError(
            "Nombre y apellido deben tener al menos una letra para generar el usuario."
        )
    return f"{first[0]}{last[:4]}"


def generate_pin() -> str:
    """PIN de 4 dígitos para el primer acceso.

    `secrets` y no `random`: este valor es una credencial, y el generador por
    defecto de Python es predecible si alguien observa suficientes salidas.
    Con ceros a la izquierda, para que las 10.000 combinaciones sean
    equiprobables — recortar "0042" a "42" dejaría un espacio sesgado.
    """
    return f"{secrets.randbelow(10_000):04d}"


def _unique_username(session, base: str) -> str:
    """`base`, o `base2`, `base3`… si ya está tomado.

    Se consulta contra `username_key` —la columna en minúsculas que usa el
    login— porque "JMERC" y "jmerc" son la misma cuenta para entrar, y ofrecer
    ambas dejaría dos filas que compiten por el mismo acceso.

    Va dentro de la transacción del alta: entre elegir el nombre y guardarlo no
    puede colarse otro con el mismo.
    """
    if not user_store.get_by_username(session, base):
        return base
    suffix = 2
    while user_store.get_by_username(session, f"{base}{suffix}"):
        suffix += 1
    return f"{base}{suffix}"


def create_documentalist(payload: DocumentalistPayload) -> DocumentalistCreated:
    """Da de alta a alguien con un PIN de primer acceso.

    El PIN se devuelve en claro UNA vez, en esta respuesta: se guarda hasheado
    como cualquier contraseña, así que no hay forma de volver a leerlo. Si se
    pierde, `reset_pin`.
    """
    _check_role(payload.role)
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    try:
        base = username_from_name(first_name, last_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    session = deps.get_session()
    try:
        username = _unique_username(session, base)
        pin = generate_pin()
        row = User(
            username=username,
            username_key=user_store.username_key(username),
            display_name=f"{first_name} {last_name}".strip(),
            first_name=first_name,
            last_name=last_name,
            password_hash=hash_password(pin),
            role=payload.role,
            is_active=True,
            must_change_password=True,
        )
        session.add(row)
        session.commit()
        # El PIN nunca al log: es una credencial viva hasta el primer acceso.
        return DocumentalistCreated(**DocumentalistResponse.model_validate(row).model_dump(), pin=pin)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("documentalist_creation_failed")
        raise HTTPException(status_code=500, detail="Error interno creando el documentalista.") from None
    finally:
        session.close()



def reset_pin(documentalist_id: int) -> DocumentalistCreated:
    """Genera un PIN nuevo y vuelve a habilitar el primer acceso.

    Hace falta porque el PIN vale una sola vez: quien entra y cierra la pantalla
    antes de elegir su contraseña queda afuera, y sin esto no habría manera de
    devolverle el acceso salvo tocando la base a mano.
    """
    session = deps.get_session()
    try:
        row = session.get(User, documentalist_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        pin = generate_pin()
        row.password_hash = hash_password(pin)
        row.must_change_password = True
        row.temp_password_used_at = None  # el PIN nuevo todavía no se usó
        session.commit()
        return DocumentalistCreated(**DocumentalistResponse.model_validate(row).model_dump(), pin=pin)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("pin_reset_failed", documentalist_id=documentalist_id)
        raise HTTPException(status_code=500, detail="Error interno regenerando el PIN.") from None
    finally:
        session.close()


def update_documentalist(documentalist_id: int, payload: DocumentalistUpdatePayload) -> DocumentalistResponse:
    """Renombra, cambia el rol, resetea la contraseña o da de baja.

    No permite cambiar el `username`: es la identidad con la que se firmaron los
    reportes ya guardados y aparece en los KPI históricos.
    """
    if payload.role is not None:
        _check_role(payload.role)

    session = deps.get_session()
    try:
        row = session.get(User, documentalist_id)
        if not row:
            raise HTTPException(status_code=404, detail="Documentalista no encontrado.")

        # Guardarraíl: `seed_operator` (db/users.py) solo crea al primer admin
        # cuando la tabla `users` está VACÍA, no cuando está poblada pero sin
        # ningún admin activo. Si esta edición le quita el rol admin o
        # desactiva al único admin activo que queda, el sistema se queda sin
        # nadie que pueda volver a dar de alta o restaurar administradores —
        # ni un reinicio del servicio lo repara, la única salida sería editar
        # la BD a mano. Por eso se corta acá, antes de aplicar el cambio.
        degrades_role = payload.role is not None and payload.role != "admin"
        deactivates = payload.is_active is False
        if row.role == "admin" and row.is_active and (degrades_role or deactivates):
            remaining_admins = session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.role == "admin",
                    User.is_active.is_(True),
                    User.id != documentalist_id,
                )
            )
            if not remaining_admins:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "No se puede dejar el sistema sin ningún administrador activo. "
                        "Asigna el rol admin a otra persona antes de retirárselo a esta."
                    ),
                )

        if payload.display_name is not None:
            row.display_name = payload.display_name.strip() or row.username
        if payload.role is not None:
            row.role = payload.role
        if payload.is_active is not None:
            row.is_active = payload.is_active
        if payload.password:
            row.password_hash = hash_password(payload.password)

        session.commit()
        return DocumentalistResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("documentalist_update_failed", documentalist_id=documentalist_id)
        raise HTTPException(
            status_code=500, detail="Error interno actualizando el documentalista."
        ) from None
    finally:
        session.close()
