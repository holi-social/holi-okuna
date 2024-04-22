from typing import Optional
import uuid
from django.db.models import Count, Q
from asgiref.sync import sync_to_async
from openbook_common.types import GeolocationFeature
from openbook_communities.models import Community as CommunityModel


def query_spaces(query: Q):
    return (
        CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
        .filter(query)
        .annotate(member_count=Count("memberships"))
        .order_by("-created")
    )


@sync_to_async
def topic_id_geolocation_query(
    topic_id: Optional[uuid.UUID] = None,
    geolocation: Optional[GeolocationFeature] = None,
) -> Q:
    query = Q()
    if topic_id is not None:
        query.add(Q(topics__id__contains=topic_id), Q.AND)
    if geolocation is not None:
        query.add(Q(geolocation__within=geolocation.geometry), Q.AND)

    return query


@sync_to_async
def geolocation_query(
    geolocation: Optional[GeolocationFeature] = None,
) -> Q:
    query = Q()
    if geolocation is not None:
        query.add(Q(geolocation__within=geolocation.geometry), Q.AND)

    return query
