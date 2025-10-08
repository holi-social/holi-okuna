import uuid
from typing import List, Optional

from asgiref.sync import sync_to_async
from django.db.models import Count, Q

from openbook_auth.models import User as UserModel
from openbook_common.types import GeolocationFeature
from openbook_communities.models import Community as CommunityModel


DISCOVER_DEFAULT_SPACES_V2 = [
    "human-rights",
    "animal-welfare",
    "climate-environment",
    "arts-culture",
    "literacy-education",
    "mental-physical-health",
    "democracy-politics",
]


@sync_to_async
def filtered_spaces(
    geolocation: Optional[GeolocationFeature] = None,
    topics_v2: Optional[List[str]] = None,
    skills_v2: Optional[List[str]] = None,
    member_id: Optional[uuid.UUID] = None,
):
    query = create_filtered_spaces_query(
        geolocation,
        topics_v2,
        skills_v2,
        member_id,
    )
    return create_spaces_queryset(query)


def create_filtered_spaces_query(
    geolocation: Optional[GeolocationFeature] = None,
    topics_v2: Optional[List[str]] = None,
    skills_v2: Optional[List[str]] = None,
    member_id: Optional[uuid.UUID] = None,
):
    query = Q()
    if geolocation is not None:
        query.add(Q(geolocation__within=geolocation.geometry), Q.AND)
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
