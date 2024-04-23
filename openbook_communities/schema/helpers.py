from typing import List, Optional
import uuid
from django.db.models import Count, Q
from asgiref.sync import sync_to_async
from openbook_common.types import GeolocationFeature
from openbook_communities.models import Community as CommunityModel
from openbook_auth.models import User as UserModel


@sync_to_async
def filtered_spaces(
    topic_id: Optional[uuid.UUID] = None,
    geolocation: Optional[GeolocationFeature] = None,
    skill_ids: Optional[List[Optional[uuid.UUID]]] = None,
    topic_slug: Optional[str] = None,
    topic_slugs: Optional[List[Optional[str]]] = None,
    skill_slugs: Optional[List[Optional[str]]] = None,
    member_id: Optional[uuid.UUID] = None,
):
    query = Q()
    if topic_id is not None:
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
    if member_id:
        user = UserModel.objects.get(username=member_id)
        query.add(Q(memberships__user=user), Q.AND)

    return (
        CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
        .filter(query)
        .annotate(member_count=Count("memberships"))
        .order_by("-created")
        .cache(ops=["fetch", "count"], timeout=300)
    )
