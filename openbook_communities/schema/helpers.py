import uuid
from typing import List, Optional

from asgiref.sync import sync_to_async
from django.db.models import Count, Q

from openbook_auth.models import User as UserModel
from openbook_common.types import GeolocationFeature
from openbook_communities.models import Community as CommunityModel


@sync_to_async
def filtered_spaces(
    topic_id: Optional[uuid.UUID] = None,
    topic_ids: Optional[List[Optional[uuid.UUID]]] = None,
    geolocation: Optional[GeolocationFeature] = None,
    skill_ids: Optional[List[Optional[uuid.UUID]]] = None,
    topic_slug: Optional[str] = None,
    topic_slugs: Optional[List[Optional[str]]] = None,
    skill_slugs: Optional[List[Optional[str]]] = None,
    topics_v2: Optional[List[str]] = None,
    skills_v2: Optional[List[str]] = None,
    member_id: Optional[uuid.UUID] = None,
):
    query = create_filtered_spaces_query(
        topic_id,
        topic_ids,
        geolocation,
        skill_ids,
        topic_slug,
        topic_slugs,
        skill_slugs,
        topics_v2,
        skills_v2,
        member_id,
    )
    return create_spaces_queryset(query)


def create_filtered_spaces_query(
    topic_id: Optional[uuid.UUID] = None,
    topic_ids: Optional[List[Optional[uuid.UUID]]] = None,
    geolocation: Optional[GeolocationFeature] = None,
    skill_ids: Optional[List[Optional[uuid.UUID]]] = None,
    topic_slug: Optional[str] = None,
    topic_slugs: Optional[List[Optional[str]]] = None,
    skill_slugs: Optional[List[Optional[str]]] = None,
    topics_v2: Optional[List[str]] = None,
    skills_v2: Optional[List[str]] = None,
    member_id: Optional[uuid.UUID] = None,
):
    query = Q()
    if topic_ids:
        if topic_id is not None:
            topic_ids.append(topic_id)
        query.add(Q(topics__id__in=topic_ids), Q.AND)
    elif topic_id is not None:
        query.add(Q(topics__id__contains=topic_id), Q.AND)
    if geolocation is not None:
        query.add(Q(geolocation__within=geolocation.geometry), Q.AND)
    if skill_ids:
        query.add(Q(tasks__skills__id__in=skill_ids), Q.AND)
    if topic_slugs:
        if topic_slug is not None:
            topic_slugs.append(topic_slug)
        query.add(Q(topics__slug__in=topic_slugs), Q.AND)
    elif topic_slug is not None:
        query.add(Q(topics__slug__contains=topic_slug), Q.AND)
    if skill_slugs:
        query.add(Q(tasks__skills__slug__in=skill_slugs), Q.AND)
    if topics_v2:
        query.add(Q(topics_v2__overlap=topics_v2), Q.AND)
    if skills_v2:
        query.add(Q(tasks__skills_v2__overlap=skills_v2), Q.AND)
    if member_id:
        user = UserModel.objects.get(username=member_id)
        query.add(Q(memberships__user=user), Q.AND)
    return query


def create_spaces_queryset(query):
    return (
        CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
        .filter(query)
        .filter(is_deleted=False)
        .annotate(member_count=Count("memberships"))
        .order_by("-created")
        .cache(ops=["fetch", "count"], timeout=300)
    )
