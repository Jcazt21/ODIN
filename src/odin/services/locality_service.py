"""Lógica de negocio del lugar de la noticia: catálogo geográfico y vínculo
con los artículos.

Los handlers HTTP (`api/routers/localities.py`) solo traducen
request/response; las queries viven aquí, igual que en `article_service.py`.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select

from odin.analysis.text_norm import norm_key
from odin.api import deps
from odin.api.deps import log
from odin.api.schemas import (
    LOCALITY_KIND_VALUES,
    LOCALITY_LEVEL_VALUES,
    LOCALITY_ORIGIN_VALUES,
    ArticleLocalityPayload,
    ArticleLocalityResponse,
    LocalityBreadcrumb,
    LocalityNode,
    LocalityPayload,
    LocalityResponse,
    LocalityUpdatePayload,
)
from odin.db.models import Article, ArticleLocality, Locality, LocalityAlias


def _path_ids(path: str) -> list[int]:
    """"/1/2/6/19/" -> [1, 2, 6, 19]."""
    return [int(part) for part in path.strip("/").split("/") if part]


def _breadcrumbs_for(session, localities: list[Locality]) -> dict[int, list[LocalityBreadcrumb]]:
    """Arma el camino país→nodo de varias localidades con UNA sola query.

    Se resuelve en lote a propósito: un artículo puede tener varias localidades
    y cada camino tiene hasta cinco nodos, así que hacerlo de a uno serían
    hasta 25 consultas por artículo listado.
    """
    needed: set[int] = set()
    for loc in localities:
        needed.update(_path_ids(loc.path))
    if not needed:
        return {}

    rows = session.scalars(select(Locality).where(Locality.id.in_(needed))).all()
    by_id = {r.id: r for r in rows}

    out: dict[int, list[LocalityBreadcrumb]] = {}
    for loc in localities:
        out[loc.id] = [
            LocalityBreadcrumb(id=n.id, name=n.name, level=n.level)
            for n in (by_id.get(i) for i in _path_ids(loc.path))
            if n is not None
        ]
    return out


def get_tree(*, include_inactive: bool = False) -> list[LocalityNode]:
    """Devuelve el árbol completo, listo para el selector en cascada.

    Se arma en memoria a partir de una sola query. El catálogo son ~204 filas
    (1 país + 3 macrorregiones + 10 regiones + 32 provincias + 158 municipios),
    así que traerlo entero es más barato que las cuatro consultas encadenadas
    que haría el frontend abriendo un desplegable tras otro.
    """
    session = deps.get_session()
    try:
        stmt = select(Locality)
        if not include_inactive:
            stmt = stmt.where(Locality.is_active.is_(True))
        rows = session.scalars(stmt.order_by(Locality.name)).all()

        # Los alias van en UNA query para todo el árbol, no con lazy-load por
        # nodo: son ~200 nodos y el N+1 se notaría en cada carga del selector.
        aliases: dict[int, list[str]] = {}
        for alias in session.scalars(select(LocalityAlias)).all():
            aliases.setdefault(alias.locality_id, []).append(alias.alias)

        nodes = {
            r.id: LocalityNode(
                id=r.id,
                name=r.name,
                level=r.level,
                parent_id=r.parent_id,
                aliases=aliases.get(r.id, []),
                children=[],
            )
            for r in rows
        }
        roots: list[LocalityNode] = []
        for r in rows:
            node = nodes[r.id]
            parent = nodes.get(r.parent_id) if r.parent_id else None
            # Un nodo cuyo padre está inactivo (o filtrado) se trata como raíz
            # en vez de descartarse: mejor mostrarlo suelto que hacerlo
            # desaparecer del selector sin explicación.
            if parent is None:
                roots.append(node)
            else:
                parent.children.append(node)
        return roots
    finally:
        session.close()


def list_localities(
    q: str | None, level: str | None, parent_id: int | None, limit: int, offset: int
) -> list[LocalityResponse]:
    """Busca lugares por nombre (sin acentos) y/o nivel y/o padre."""
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    session = deps.get_session()
    try:
        stmt = select(Locality)
        if q:
            # norm_key ya está guardado sin acentos ni mayúsculas, así que un
            # LIKE sobre esa columna basta y aprovecha su índice; no hace falta
            # el regex `~*` que usan las búsquedas de texto libre.
            stmt = stmt.where(Locality.norm_key.like(f"%{norm_key(q)}%"))
        if level:
            stmt = stmt.where(Locality.level == level)
        if parent_id is not None:
            stmt = stmt.where(Locality.parent_id == parent_id)
        rows = session.scalars(
            stmt.order_by(Locality.level, Locality.name).limit(limit).offset(offset)
        ).all()
        return [LocalityResponse.model_validate(r) for r in rows]
    finally:
        session.close()


def create_locality(payload: LocalityPayload) -> LocalityResponse:
    """Agrega un lugar al catálogo — el caso real es un municipio creado por
    ley, que debe poder entrar sin deploy ni migración."""
    if payload.level not in LOCALITY_LEVEL_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"Nivel inválido: '{payload.level}'. Válidos: {', '.join(LOCALITY_LEVEL_VALUES)}.",
        )
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="El nombre no puede estar vacío.")

    session = deps.get_session()
    try:
        parent = None
        if payload.parent_id is not None:
            parent = session.get(Locality, payload.parent_id)
            if not parent:
                raise HTTPException(status_code=404, detail="El lugar padre no existe.")
        elif payload.level != "PAIS":
            raise HTTPException(
                status_code=422, detail="Solo un país puede no tener lugar padre."
            )

        nkey = norm_key(name)
        clash = session.scalar(
            select(Locality).where(
                Locality.parent_id == payload.parent_id, Locality.norm_key == nkey
            )
        )
        if clash:
            raise HTTPException(
                status_code=409, detail=f"'{name}' ya existe dentro de ese lugar padre."
            )

        row = Locality(
            name=name, norm_key=nkey, level=payload.level, parent_id=payload.parent_id, path=""
        )
        session.add(row)
        session.flush()  # necesitamos el id para armar el path
        row.path = f"{parent.path if parent else '/'}{row.id}/"
        session.commit()
        return LocalityResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("locality_creation_failed")
        raise HTTPException(status_code=500, detail="Error interno creando el lugar.") from None
    finally:
        session.close()


def update_locality(locality_id: int, payload: LocalityUpdatePayload) -> LocalityResponse:
    """Renombra o desactiva un lugar. No mueve nodos de padre: eso obligaría a
    reescribir el `path` de todo el subárbol, y no es un caso real (los
    municipios no cambian de provincia)."""
    session = deps.get_session()
    try:
        row = session.get(Locality, locality_id)
        if not row:
            raise HTTPException(status_code=404, detail="Lugar no encontrado.")
        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="El nombre no puede estar vacío.")
            row.name = name
            row.norm_key = norm_key(name)
        if payload.is_active is not None:
            row.is_active = payload.is_active
        session.commit()
        return LocalityResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("locality_update_failed", locality_id=locality_id)
        raise HTTPException(status_code=500, detail="Error interno actualizando el lugar.") from None
    finally:
        session.close()


def _serialize_links(session, links: list[ArticleLocality]) -> list[ArticleLocalityResponse]:
    crumbs = _breadcrumbs_for(session, [link.locality for link in links])
    return [
        ArticleLocalityResponse(
            id=link.id,
            locality_id=link.locality_id,
            name=link.locality.name,
            level=link.locality.level,
            kind=link.kind,
            origin=link.origin,
            confidence=link.confidence,
            breadcrumb=crumbs.get(link.locality_id, []),
        )
        for link in links
    ]


def list_article_localities(article_id: int) -> list[ArticleLocalityResponse]:
    session = deps.get_session()
    try:
        if not session.get(Article, article_id):
            raise HTTPException(status_code=404, detail="Artículo no encontrado.")
        links = session.scalars(
            select(ArticleLocality).where(ArticleLocality.article_id == article_id)
        ).all()
        return _serialize_links(session, list(links))
    finally:
        session.close()


def _validate_link_payload(payload: ArticleLocalityPayload) -> None:
    if payload.kind not in LOCALITY_KIND_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"Papel inválido: '{payload.kind}'. Válidos: {', '.join(LOCALITY_KIND_VALUES)}.",
        )
    if payload.origin not in LOCALITY_ORIGIN_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"Origen inválido: '{payload.origin}'. Válidos: {', '.join(LOCALITY_ORIGIN_VALUES)}.",
        )


def validate_link_payloads(
    session, payloads: list[ArticleLocalityPayload]
) -> list[ArticleLocalityPayload]:
    """Valida papel, origen, duplicados y existencia de los lugares.

    Se comparte entre el reemplazo sobre un artículo ya guardado y el alta
    manual, que los crea junto con el artículo. Vive aquí y no en
    `article_service` porque las reglas son del catálogo de lugares; que el
    alta valide ANTES de insertar nada es lo que hace atómico el guardado del
    formulario.

    Devuelve los vínculos deduplicados, en el orden en que llegaron.
    """
    for payload in payloads:
        _validate_link_payload(payload)

    wanted = {(p.locality_id, p.kind): p for p in payloads}
    if len(wanted) != len(payloads):
        raise HTTPException(
            status_code=422, detail="Hay lugares repetidos con el mismo papel."
        )

    if not payloads:
        return []

    found = session.scalars(
        select(Locality.id).where(Locality.id.in_([p.locality_id for p in payloads]))
    ).all()
    missing = {p.locality_id for p in payloads} - set(found)
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Lugares inexistentes: {', '.join(str(m) for m in sorted(missing))}.",
        )
    return list(wanted.values())


def add_article_locality(
    article_id: int, payload: ArticleLocalityPayload
) -> ArticleLocalityResponse:
    """Vincula un lugar a un artículo (el botón "Agregar" del formulario)."""
    _validate_link_payload(payload)
    session = deps.get_session()
    try:
        if not session.get(Article, article_id):
            raise HTTPException(status_code=404, detail="Artículo no encontrado.")
        locality = session.get(Locality, payload.locality_id)
        if not locality:
            raise HTTPException(status_code=404, detail="Lugar no encontrado.")

        existing = session.scalar(
            select(ArticleLocality).where(
                ArticleLocality.article_id == article_id,
                ArticleLocality.locality_id == payload.locality_id,
                ArticleLocality.kind == payload.kind,
            )
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"'{locality.name}' ya está vinculado a este artículo como {payload.kind}.",
            )

        link = ArticleLocality(
            article_id=article_id,
            locality_id=payload.locality_id,
            kind=payload.kind,
            origin=payload.origin,
            confidence=payload.confidence,
        )
        session.add(link)
        session.commit()
        return _serialize_links(session, [link])[0]
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("article_locality_add_failed", article_id=article_id)
        raise HTTPException(status_code=500, detail="Error interno vinculando el lugar.") from None
    finally:
        session.close()


def replace_article_localities(
    article_id: int, payloads: list[ArticleLocalityPayload]
) -> list[ArticleLocalityResponse]:
    """Deja el artículo exactamente con los lugares indicados.

    Es lo que usa el guardado del formulario: el documentalista ve una lista y
    la envía completa, así que reemplazar es más fiel a esa interacción que
    calcular altas y bajas en el frontend.
    """
    session = deps.get_session()
    try:
        if not session.get(Article, article_id):
            raise HTTPException(status_code=404, detail="Artículo no encontrado.")

        wanted_links = validate_link_payloads(session, payloads)

        for link in session.scalars(
            select(ArticleLocality).where(ArticleLocality.article_id == article_id)
        ).all():
            session.delete(link)
        session.flush()

        links = [
            ArticleLocality(
                article_id=article_id,
                locality_id=p.locality_id,
                kind=p.kind,
                origin=p.origin,
                confidence=p.confidence,
            )
            for p in wanted_links
        ]
        session.add_all(links)
        session.commit()
        return _serialize_links(session, links)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("article_localities_replace_failed", article_id=article_id)
        raise HTTPException(
            status_code=500, detail="Error interno guardando los lugares."
        ) from None
    finally:
        session.close()


def delete_article_locality(article_id: int, link_id: int) -> None:
    session = deps.get_session()
    try:
        link = session.scalar(
            select(ArticleLocality).where(
                ArticleLocality.id == link_id, ArticleLocality.article_id == article_id
            )
        )
        if not link:
            raise HTTPException(status_code=404, detail="Vínculo no encontrado.")
        session.delete(link)
        session.commit()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("article_locality_delete_failed", link_id=link_id)
        raise HTTPException(
            status_code=500, detail="Error interno eliminando el vínculo."
        ) from None
    finally:
        session.close()


def frequency_by_locality(
    level: str, date_from: str | None, date_to: str | None, kind: str = "HECHO"
) -> list[dict]:
    """Cuántas noticias por lugar, agregando a un nivel dado.

    El roll-up es el punto: una noticia marcada en Tamboril cuenta para
    Santiago y para el Cibao sin haberla etiquetado tres veces. Se logra
    comparando el `path` del nodo del nivel pedido con el de la localidad de
    cada artículo — la relación ancestro/descendiente ya está materializada
    ahí, así que no hace falta recursión.
    """
    if level not in LOCALITY_LEVEL_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"Nivel inválido: '{level}'. Válidos: {', '.join(LOCALITY_LEVEL_VALUES)}.",
        )

    session = deps.get_session()
    try:
        ancestor = Locality.__table__.alias("ancestor")
        stmt = (
            select(
                ancestor.c.id,
                ancestor.c.name,
                func.count(func.distinct(ArticleLocality.article_id)).label("articles"),
            )
            .select_from(ArticleLocality)
            .join(Locality, Locality.id == ArticleLocality.locality_id)
            .join(ancestor, Locality.path.like(ancestor.c.path + "%"))
            .where(ancestor.c.level == level, ArticleLocality.kind == kind)
            .group_by(ancestor.c.id, ancestor.c.name)
            .order_by(func.count(func.distinct(ArticleLocality.article_id)).desc())
        )

        if date_from or date_to:
            from odin.services.article_service import _parse_date

            stmt = stmt.join(Article, Article.id == ArticleLocality.article_id)
            if date_from and (parsed := _parse_date(date_from)):
                stmt = stmt.where(Article.published_at >= parsed)
            if date_to and (parsed := _parse_date(date_to)):
                from datetime import timedelta

                stmt = stmt.where(Article.published_at < parsed + timedelta(days=1))

        return [
            {"locality_id": row.id, "name": row.name, "articles": row.articles}
            for row in session.execute(stmt).all()
        ]
    finally:
        session.close()
