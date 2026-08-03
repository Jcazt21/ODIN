"""Modelos de base de datos (SQLAlchemy 2.0).

Diseñados para ser portables entre PostgreSQL (desarrollo) y SQL Server (cliente):
se usan tipos genéricos del ORM, sin funciones específicas de un motor.

Estructura:
  Article     -> un artículo de periódico con su análisis global.
  Entity      -> una figura pública o empresa mencionada, con la opinión hacia ella.
  EntityAlias -> sigla ("MINERD") y su nombre canónico, editable desde el frontend.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Identificación / procedencia ---
    source: Mapped[str] = mapped_column(String(100), index=True)   # p.ej. "listin_diario"
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    title: Mapped[str] = mapped_column(String(600))
    authors: Mapped[str | None] = mapped_column(String(500))        # autores separados por ", "
    section: Mapped[str | None] = mapped_column(String(200))        # sección / categoría
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # --- Contenido ---
    body: Mapped[str | None] = mapped_column(Text)

    # --- Análisis global ("de qué se habla" y si es bueno/malo/neutro) ---
    main_topic: Mapped[str | None] = mapped_column(String(200))       # tema principal, p.ej. "agua potable"
    topic_keywords: Mapped[str | None] = mapped_column(String(600))   # palabras clave separadas por ", "
    overall_sentiment: Mapped[str | None] = mapped_column(String(10)) # "POS" | "NEG" | "NEU"
    sentiment_score: Mapped[float | None] = mapped_column(Float)      # confianza 0..1

    # --- Análisis de encuadre (solo GeminiAnalyzer; NULL con LocalAnalyzer) ---
    framing: Mapped[str | None] = mapped_column(String(40))           # crisis_conflicto | logro_institucional | ...
    headline_intent: Mapped[str | None] = mapped_column(String(20))   # informativo | alarmista | sensacionalista
    lead_orientation: Mapped[str | None] = mapped_column(String(20))  # social | oficialista | tecnico
    dominant_actor: Mapped[str | None] = mapped_column(String(300))   # entidad con más peso en la nota
    source_quality: Mapped[str | None] = mapped_column(String(30))    # citas_directas | testimonios_anonimos | ...
    has_hard_data: Mapped[bool | None] = mapped_column(Boolean)       # ¿hay cifras verificables?
    blamed_actor: Mapped[str | None] = mapped_column(String(300))     # señalado como causante
    credited_actor: Mapped[str | None] = mapped_column(String(300))   # presentado como solución

    entities: Mapped[list["Entity"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Article {self.source}: {self.title[:40]!r}>"


class Entity(Base):
    """Figura pública o empresa mencionada, con la opinión que el artículo expresa hacia ella."""

    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("article_id", "name", "type", name="uq_entity_per_article"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(300), index=True)     # p.ej. "Luis Abinader"
    type: Mapped[str] = mapped_column(String(20))                  # "PERSON" | "ORG"
    mentions_count: Mapped[int] = mapped_column(Integer, default=1)

    # --- Opinión hacia la entidad (¿hablan bien o mal de ella?) ---
    sentiment_toward: Mapped[str | None] = mapped_column(String(10))  # "POS" | "NEG" | "NEU"
    sentiment_score: Mapped[float | None] = mapped_column(Float)      # confianza 0..1
    context: Mapped[str | None] = mapped_column(Text)                 # frase(s) de ejemplo

    article: Mapped["Article"] = relationship(back_populates="entities")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Entity {self.name} ({self.type}) {self.sentiment_toward}>"


class EntityAlias(Base):
    """Sigla de una organización y el nombre completo al que equivale.

    Resuelve dos casos que la heurística de `LocalAnalyzer` no puede:
      * siglas silábicas (MINERD, INTRANT, SENASA), que no son las iniciales
        del nombre completo y por tanto no se pueden inferir;
      * unificar sigla y nombre completo aunque aparezcan en artículos
        distintos (la fusión automática solo ve un artículo a la vez).

    El catálogo se siembra desde `db/seed_aliases.py` y a partir de ahí se
    administra desde el frontend (CRUD).
    """

    __tablename__ = "entity_aliases"
    __table_args__ = (
        UniqueConstraint("alias_key", "type", name="uq_alias_per_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    alias: Mapped[str] = mapped_column(String(100))                 # "MINERD" (como se muestra)
    alias_key: Mapped[str] = mapped_column(String(100), index=True) # "minerd" (normalizado, para buscar)
    canonical_name: Mapped[str] = mapped_column(String(300))        # "Ministerio de Educación..."
    type: Mapped[str] = mapped_column(String(20), default="ORG")    # "PERSON" | "ORG"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # desactivar sin borrar

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EntityAlias {self.alias} -> {self.canonical_name}>"
