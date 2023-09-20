import uuid
from typing import Annotated, List, Optional

import strawberry
import strawberry_django
from asgiref.sync import async_to_sync, sync_to_async
from django.db.models import Count, Prefetch, Q
from django.utils.translation import gettext_lazy as _
from graphql import GraphQLError

from openbook_auth.models import User as UserModel
from openbook_auth.utils import verify_authorized_user
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.schema.types import GeoJSON, Paged
from openbook_common.types import GeolocationFeature
from openbook_common.utils.helpers import is_uuid
from openbook_communities.models import CollaborationTool as CollaborationToolModel
from openbook_communities.models import Community as CommunityModel
from openbook_communities.models import SpaceUserConnectionType
from openbook_communities.models import Task as TaskModel
from openbook_communities.schema.types import (
    CollaborationTool,
    DiscoverSpaces,
    MySpaces,
    Space,
    Task,
)
from openbook_moderation.models import ModeratedObject as ModeratedObjectModel


@sync_to_async
def spaces_for_filter(
    offset: int,
    limit: int,
    topic_id: Optional[uuid.UUID] = None,
    geolocation: Optional[GeolocationFeature] = None,
    skill_ids: Optional[List[Optional[uuid.UUID]]] = None,
    topic_slug: Optional[str] = None,
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
    if topic_slug is not None:
        query.add(Q(topics__slug__contains=topic_slug), Q.AND)
    if skill_slugs:
        query.add(Q(tasks__skills__slug__in=skill_slugs), Q.AND)
    if member_id:
        user = UserModel.objects.get(username=member_id)
        query.add(Q(memberships__user=user), Q.AND)

    return Paged.of(
        CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
        .filter(query)
        .annotate(member_count=Count("memberships"))
        .order_by("-created")
        .cache(ops=["fetch", "count"], timeout=300),
        offset,
        limit,
    )


@strawberry.type
class Query:
    @strawberry_django.field()
    async def spaces(
        self,
        topic_id: Optional[uuid.UUID] = None,
        location: Annotated[
            Optional[str],
            strawberry.argument(
                # Using description instead of deprecation_reason as deprecated arguments are removed in GraphQL Mesh
                description="Unsupported since version 1.0.16, use geolocation instead",
            ),
        ] = None,
        geolocation: Optional[GeoJSON] = None,
        skill_ids: Optional[List[Optional[uuid.UUID]]] = None,
        topic_slug: Optional[str] = None,
        skill_slugs: Optional[List[Optional[str]]] = None,
        member_id: Optional[uuid.UUID] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[Space]:
        return await spaces_for_filter(
            offset,
            limit,
            topic_id,
            geolocation,
            skill_ids,
            topic_slug,
            skill_slugs,
            member_id,
        )

    @strawberry_django.field()
    def discover_spaces(
        self,
        info,
        topic_ids: Optional[List[Optional[uuid.UUID]]] = None,
        location: Annotated[
            Optional[str],
            # Using description instead of deprecation_reason as deprecated arguments are removed in GraphQL Mesh
            strawberry.argument(description="Unsupported since version 1.0.16, use geolocation instead"),
        ] = None,
        geolocation: Optional[GeoJSON] = None,
        skill_ids: Optional[List[Optional[uuid.UUID]]] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> List[Optional[DiscoverSpaces]]:
        result = []

        # get all spaces by geolocation (independent of other filters)
        if geolocation is not None:
            result.append(
                DiscoverSpaces(
                    location_id=geolocation.id,
                    spaces=async_to_sync(spaces_for_filter)(
                        geolocation=geolocation,
                        offset=offset,
                        limit=limit,
                    ),
                )
            )

        # get all spaces by topic (independent of other filters)
        if topic_ids is not None:
            for topic_id in topic_ids:
                result.append(
                    DiscoverSpaces(
                        topic_id=topic_id,
                        spaces=async_to_sync(spaces_for_filter)(
                            topic_id=topic_id,
                            offset=offset,
                            limit=limit,
                        ),
                    )
                )

        # get all spaces by skill_id (including geolocation filter)
        if skill_ids is not None:
            for skill_id in skill_ids:
                result.append(
                    DiscoverSpaces(
                        skill_id=skill_id,
                        location_id=geolocation.id if geolocation else None,
                        spaces=async_to_sync(spaces_for_filter)(
                            skill_ids=skill_ids,
                            geolocation=geolocation,
                            offset=offset,
                            limit=limit,
                        ),
                    )
                )
        return result

    @strawberry_django.field()
    def my_spaces(self, info) -> List[Optional[MySpaces]]:
        current_user = verify_authorized_user(info)

        created_spaces = MySpaces(section=_("Created"), type=SpaceUserConnectionType.CREATOR)
        created_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
            .filter(creator=current_user)
            .order_by("-created")
        )
        member_spaces = MySpaces(section=_("Joined"), type=SpaceUserConnectionType.MEMBER)
        member_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
            .filter(Q(memberships__user=current_user), ~Q(creator=current_user))
            .order_by("-created")
        )
        followed_spaces = MySpaces(section=_("Following"), type=SpaceUserConnectionType.FOLLOWER)
        followed_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
            .filter(
                Q(notifications_subscriptions__subscriber=current_user),
                Q(notifications_subscriptions__new_post_notifications=True),
                ~Q(creator=current_user),
                ~Q(memberships__user=current_user),
            )
            .order_by("-created")
        )
        return list(
            filter(
                lambda x: x.query.count() > 0,
                [created_spaces, member_spaces, followed_spaces],
            )
        )

    @strawberry_django.field()
    def space_by_id(
        self,
        info,
        id_or_name: Annotated[
            str,
            strawberry.argument(
                description="idOrName can either be the space id or name (slug). If none of them is found, an error with the message 'Space not found' is thrown."
            ),
        ],
    ) -> Optional[Space]:
        user = info.context.request.user

        # check if current user is member of the community to filter out members-only tasks
        is_member = False
        is_anonymous = user.is_anonymous

        if not is_anonymous and is_uuid(id_or_name):
            is_member = user.is_member_of_community_with_id(community_id=id_or_name)
        elif not is_anonymous:
            is_member = user.is_member_of_community_with_name(community_name=id_or_name)

        query = Q(id=uuid.UUID(id_or_name)) if is_uuid(id_or_name) else Q(name=id_or_name)

        tasks_query = Q()

        if not is_member:
            tasks_query.add(Q(visibility="PUBLIC"), Q.AND)

        try:
            return (
                CommunityModel.objects.prefetch_related(
                    "links",
                    "memberships__user__profile",
                    Prefetch("tasks", queryset=TaskModel.objects.filter(tasks_query)),
                )
                .filter(
                    ModeratedObjectModel.not_moderated_query(
                        info.context.request.user, ModeratedObjectModel.OBJECT_TYPE_COMMUNITY
                    )
                )
                .get(query)
            )
        except CommunityModel.DoesNotExist:
            raise GraphQLError("Space not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

    @strawberry_django.field()
    def tasks_by_space_id(self, space_id: uuid.UUID, offset: int = 0, limit: int = 10) -> Paged[Task]:
        return Paged.of(
            TaskModel.objects.filter(community__id=space_id).order_by("-created"),
            offset,
            limit,
        )

    @strawberry_django.field()
    def task_by_id(self, id: uuid.UUID) -> Optional[Task]:
        try:
            return TaskModel.objects.get(id=id)
        except TaskModel.DoesNotExist:
            raise GraphQLError("Task not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

    @strawberry_django.field()
    def collaboration_tools(self, space_id: uuid.UUID, offset: int = 0, limit: int = 10) -> Paged[CollaborationTool]:
        return Paged.of(
            CollaborationToolModel.objects.filter(community__id=space_id).order_by("-created_at"),
            offset,
            limit,
        )
