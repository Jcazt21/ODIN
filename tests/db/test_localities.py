"""Pruebas del catálogo geográfico (`odin/db/localities.py`).

La cifra que se verifica aquí no es arbitraria: la División Territorial de la
ONE y el Decreto 710-04 dan 31 provincias + el Distrito Nacional y 158
municipios, agrupados en 10 regiones de planificación y 3 macrorregiones. Si
un cambio deja el catálogo en otra cifra, es un error de datos, no un test
desactualizado — salvo que haya salido una ley nueva, en cuyo caso hay que
actualizar la semilla Y este número a la vez.
"""
from __future__ import annotations

from sqlalchemy import func, select

import odin.db.localities as loc_store
from odin.db.models import Locality, LocalityAlias


def _count(session, level: str) -> int:
    return session.scalar(
        select(func.count()).select_from(Locality).where(Locality.level == level)
    )


class TestSeed:
    def test_loads_official_territorial_division(self, db_session):
        loc_store.seed_localities(db_session)

        assert _count(db_session, "PAIS") == 1
        assert _count(db_session, "MACRORREGION") == 3
        assert _count(db_session, "REGION") == 10
        assert _count(db_session, "PROVINCIA") == 32  # 31 provincias + Distrito Nacional
        assert _count(db_session, "MUNICIPIO") == 158

    def test_is_idempotent(self, db_session):
        first = loc_store.seed_localities(db_session)
        second = loc_store.seed_localities(db_session)

        assert first > 0
        assert second == 0, "la segunda corrida no debe insertar nada"
        assert _count(db_session, "MUNICIPIO") == 158

    def test_national_district_has_no_municipalities(self, db_session):
        """El DN no es provincia ni se divide en municipios: modelarlo con uno
        propio inflaría el conteo nacional a 159."""
        loc_store.seed_localities(db_session)
        dn = loc_store.resolve(db_session, "Distrito Nacional")

        assert dn is not None
        assert dn.children == []

    def test_includes_municipalities_created_in_2024(self, db_session):
        """La Victoria (Ley 15-24, vigente desde 2026-01-01) y La Caleta (Ley
        39-24) elevaron Santo Domingo de 7 a 9 municipios."""
        loc_store.seed_localities(db_session)
        santo_domingo = loc_store.resolve(db_session, "Santo Domingo", level="PROVINCIA")

        names = {m.name for m in santo_domingo.children}
        assert "La Victoria" in names
        assert "La Caleta" in names
        assert len(names) == 9


class TestPath:
    def test_child_path_extends_parent_path(self, db_session):
        loc_store.seed_localities(db_session)
        tamboril = loc_store.resolve(db_session, "Tamboril")
        santiago = tamboril.parent

        assert tamboril.path.startswith(santiago.path)
        assert tamboril.path.endswith(f"/{tamboril.id}/")

    def test_path_is_delimited_on_both_ends(self, db_session):
        """Sin la barra final, LIKE '/1/2%' matchearía también al id 20."""
        loc_store.seed_localities(db_session)
        for row in db_session.scalars(select(Locality).limit(20)).all():
            assert row.path.startswith("/")
            assert row.path.endswith("/")

    def test_full_chain_from_country_to_municipality(self, db_session):
        loc_store.seed_localities(db_session)
        node = loc_store.resolve(db_session, "Tamboril")

        chain = []
        while node:
            chain.append(node.level)
            node = node.parent

        assert chain == ["MUNICIPIO", "PROVINCIA", "REGION", "MACRORREGION", "PAIS"]


class TestResolve:
    def test_finds_by_exact_name(self, db_session):
        loc_store.seed_localities(db_session)
        assert loc_store.resolve(db_session, "Bonao").level == "MUNICIPIO"

    def test_is_accent_insensitive(self, db_session):
        loc_store.seed_localities(db_session)
        with_accent = loc_store.resolve(db_session, "Samaná")
        without = loc_store.resolve(db_session, "Samana")

        assert with_accent is not None
        assert with_accent.id == without.id

    def test_finds_former_province_name_by_alias(self, db_session):
        """La prensa sigue diciendo "Salcedo" por Hermanas Mirabal (renombrada
        en 2007)."""
        loc_store.seed_localities(db_session)
        found = loc_store.resolve(db_session, "Salcedo", level="PROVINCIA")

        assert found is not None
        assert found.name == "Hermanas Mirabal"

    def test_finds_municipality_by_common_alias(self, db_session):
        """Villa Bisonó aparece en los medios casi siempre como "Navarrete"."""
        loc_store.seed_localities(db_session)
        found = loc_store.resolve(db_session, "Navarrete")

        assert found is not None
        assert found.name == "Villa Bisonó"

    def test_level_filter_disambiguates_homonyms(self, db_session):
        """"Santiago" es provincia y también el nombre corto de su municipio
        cabecera; sin el filtro de nivel la respuesta sería ambigua."""
        loc_store.seed_localities(db_session)
        provincia = loc_store.resolve(db_session, "Santiago", level="PROVINCIA")

        assert provincia.level == "PROVINCIA"

    def test_returns_none_for_unknown_place(self, db_session):
        loc_store.seed_localities(db_session)
        assert loc_store.resolve(db_session, "Wakanda") is None

    def test_alias_identical_to_name_is_not_stored(self, db_session):
        """Un alias igual al nombre no aporta y ensucia la tabla."""
        loc_store.seed_localities(db_session)
        rows = db_session.scalars(
            select(LocalityAlias).join(Locality, Locality.id == LocalityAlias.locality_id)
        ).all()

        for alias in rows:
            assert alias.alias_key != alias.locality.norm_key


class TestSubtreePrefix:
    def test_prefix_matches_node_and_descendants(self, db_session):
        loc_store.seed_localities(db_session)
        santiago = loc_store.resolve(db_session, "Santiago", level="PROVINCIA")

        rows = db_session.scalars(
            select(Locality).where(Locality.path.like(loc_store.subtree_prefix(santiago)))
        ).all()

        names = {r.name for r in rows}
        assert "Santiago" in names, "el nodo mismo debe entrar"
        assert "Tamboril" in names, "y sus municipios también"
        assert "Bonao" not in names, "pero no los de otra provincia"
