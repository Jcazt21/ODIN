"""Catálogo administrable de temas y clasificación de la noticia."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from odin.api.schemas import (
    ArticleSummary,
    ArticleTopicPayload,
    ArticleTopicResponse,
    TopicAliasPayload,
    TopicAliasResponse,
    TopicFrequencyRow,
    TopicNode,
    TopicPayload,
    TopicResponse,
    TopicUpdatePayload,
)
from odin.core import auth
from odin.services import topic_service

router = APIRouter(tags=["topics"])


@router.get("/api/topics/tree", response_model=list[TopicNode])
def topic_tree(include_inactive: bool = False):
    return topic_service.get_tree(include_inactive=include_inactive)


@router.get("/api/topics/frequency", response_model=list[TopicFrequencyRow])
def topic_frequency(date_from: str | None = None, date_to: str | None = None,
                    parent_id: int | None = None):
    return topic_service.frequency_by_topic(date_from, date_to, parent_id)


@router.get("/api/topics/unclassified", response_model=list[ArticleSummary])
def unclassified(limit: int = 20, offset: int = 0):
    return topic_service.list_unclassified(limit, offset)


@router.get("/api/topics", response_model=list[TopicResponse])
def list_topics(q: str | None = None, parent_id: int | None = None,
                include_inactive: bool = False, limit: int = 200, offset: int = 0):
    return topic_service.list_topics(q, parent_id, include_inactive, limit, offset)


@router.post("/api/topics", status_code=201,
             dependencies=[Depends(auth.require_auth)], response_model=TopicResponse)
def create_topic(payload: TopicPayload):
    return topic_service.create_topic(payload)


@router.put("/api/topics/{topic_id}", dependencies=[Depends(auth.require_auth)],
            response_model=TopicResponse)
def update_topic(topic_id: int, payload: TopicUpdatePayload):
    return topic_service.update_topic(topic_id, payload)


@router.delete("/api/topics/{topic_id}", status_code=204,
               dependencies=[Depends(auth.require_auth)])
def delete_topic(topic_id: int):
    topic_service.delete_topic(topic_id)


@router.post("/api/topics/{topic_id}/aliases", status_code=201,
             dependencies=[Depends(auth.require_auth)], response_model=TopicAliasResponse)
def add_alias(topic_id: int, payload: TopicAliasPayload):
    return topic_service.add_alias(topic_id, payload)


@router.delete("/api/topics/{topic_id}/aliases/{alias_id}", status_code=204,
               dependencies=[Depends(auth.require_auth)])
def delete_alias(topic_id: int, alias_id: int):
    topic_service.delete_alias(topic_id, alias_id)


@router.get("/api/articles/{article_id}/topics", response_model=list[ArticleTopicResponse])
def list_article_topics(article_id: int):
    return topic_service.list_article_topics(article_id)


@router.put("/api/articles/{article_id}/topics",
            dependencies=[Depends(auth.require_auth)], response_model=list[ArticleTopicResponse])
def replace_article_topics(article_id: int, payload: list[ArticleTopicPayload],
                           documentalist: str = Depends(auth.require_auth)):
    return topic_service.replace_article_topics(
        article_id, [p.topic_id for p in payload], documentalist_username=documentalist)
