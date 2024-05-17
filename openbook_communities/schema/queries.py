import uuid
from typing import Annotated, List, Optional, Any, TypeAlias

import strawberry
import strawberry_django
from asgiref.sync import async_to_sync
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch, F, Q, Case, When, Value, IntegerField
from django.db.models.lookups import IContains
from django.utils.translation import gettext_lazy as _
from strawberry.django.context import StrawberryDjangoContext
from strawberry.types import Info as StrawberryInfo

from openbook_auth.models import User as UserModel
from openbook_auth.utils import verify_authorized_user
from openbook_common.schema.types import GeoJSON, Paged
from openbook_common.utils.helpers import is_uuid
from openbook_common.validators import string_not_empty
from openbook_communities.models import CollaborationTool as CollaborationToolModel
from openbook_communities.models import Community as CommunityModel
from openbook_communities.models import SpaceUserConnectionType
from openbook_communities.models import Task as TaskModel
from openbook_communities.models import Topic as TopicModel
from openbook_communities.schema.helpers import (
    filtered_spaces,
    create_filtered_spaces_query,
)
from openbook_communities.schema.types import (
    CollaborationTool,
    DiscoverSpaces,
    MySpaces,
    Space,
    Task,
)

Info: TypeAlias = StrawberryInfo[StrawberryDjangoContext, Any]


@strawberry.type
class Query:
    @strawberry_django.field()
    def spaces(
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
        topic_slugs: Optional[List[Optional[str]]] = None,
        skill_slugs: Optional[List[Optional[str]]] = None,
        member_id: Optional[uuid.UUID] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[Space]:
        spaces = async_to_sync(filtered_spaces)(
            topic_id=topic_id,
            geolocation=geolocation,
            skill_ids=skill_ids,
            topic_slug=topic_slug,
            topic_slugs=topic_slugs,
            skill_slugs=skill_slugs,
            member_id=member_id,
        )

        return Paged.of(spaces, offset, limit)

    @strawberry_django.field()
    def recommended_spaces(
        self,
        info,
        offset: int = 0,
        limit: int = 5,
    ) -> Paged[Space]:
        current_user = info.context.request.user

        whens = []

        if current_user and not current_user.is_anonymous:
            topic_ids = list(current_user.profile.interests.values_list("id", flat=True).all())
            geolocation = current_user.geolocation

            if topic_ids:
                whens.append(
                    When(create_filtered_spaces_query(topic_ids=topic_ids, geolocation=geolocation), then=Value(10))
                )

            if geolocation:
                whens.append(When(create_filtered_spaces_query(geolocation=geolocation), then=Value(20)))

        default_topics = list(TopicModel.objects.filter(is_discover_spaces_default=True).values_list("id", flat=True))
        if default_topics:
            whens.append(When(create_filtered_spaces_query(topic_ids=default_topics), then=Value(30)))

        return Paged.of(
            CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
            .annotate(member_count=Count("memberships"))
            .annotate(
                custom_order=Case(
                    *whens,
                    output_field=IntegerField(),
                )
            )
            .filter(custom_order__isnull=False)
            .distinct()
            .order_by("custom_order", "-created")
            .cache(ops=["fetch", "count"], timeout=300),
            offset,
            limit,
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
            spaces = async_to_sync(filtered_spaces)(geolocation=geolocation)
            result.append(
                DiscoverSpaces(
                    location_id=geolocation.id,
                    spaces=Paged.of(spaces, offset, limit),
                )
            )

        # get all spaces by topic (independent of other filters)
        if topic_ids is not None:
            for topic_id in topic_ids:
                spaces = async_to_sync(filtered_spaces)(topic_id=topic_id)
                result.append(
                    DiscoverSpaces(
                        topic_id=topic_id,
                        spaces=Paged.of(spaces, offset, limit),
                    )
                )

        # get all spaces by skill_id (including geolocation filter)
        if skill_ids is not None:
            for skill_id in skill_ids:
                spaces = async_to_sync(filtered_spaces)(skill_ids=skill_ids, geolocation=geolocation)
                result.append(
                    DiscoverSpaces(
                        skill_id=skill_id,
                        location_id=geolocation.id if geolocation else None,
                        spaces=Paged.of(spaces, offset, limit),
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
        invited_spaces = MySpaces(section=_("Invited"), type=SpaceUserConnectionType.MEMBERSHIP_INVITEE)
        invited_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "invites__invited_user__profile")
            .filter(Q(invites__invited_user=current_user))
            .order_by("-created")
        )
        requested_spaces = MySpaces(section=_("Requested"), type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR)
        requested_spaces.query = (
            CommunityModel.objects.prefetch_related(
                "links", "invites__invited_user__profile", "membership_requests__user__profile"
            )
            .filter(
                Q(membership_requests__user=current_user),
                ~Q(invites__invited_user=current_user),
            )
            .order_by("-created")
        )
        followed_spaces = MySpaces(section=_("Following"), type=SpaceUserConnectionType.FOLLOWER)
        followed_spaces.query = (
            CommunityModel.objects.prefetch_related(
                "links",
                "memberships__user__profile",
                "membership_requests__user__profile",
                "invites__invited_user__profile",
            )
            .filter(
                Q(notifications_subscriptions__subscriber=current_user),
                Q(notifications_subscriptions__new_post_notifications=True),
                ~Q(creator=current_user),
                ~Q(memberships__user=current_user),
                ~Q(invites__invited_user=current_user),
                ~Q(membership_requests__user=current_user),
            )
            .order_by("-created")
        )
        return list(
            filter(
                lambda x: x.query.count() > 0,
                [created_spaces, member_spaces, requested_spaces, invited_spaces, followed_spaces],
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

        return (
            CommunityModel.objects.prefetch_related(
                "links",
                "memberships__user__profile",
                Prefetch("tasks", queryset=TaskModel.objects.filter(tasks_query).order_by("-created")),
            )
            .filter(is_deleted=False)
            .get(query)
        )

    @strawberry_django.field()
    def tasks_by_space_id(self, space_id: uuid.UUID, offset: int = 0, limit: int = 10) -> Paged[Task]:
        return Paged.of(
            TaskModel.objects.filter(community__id=space_id).order_by("-created"),
            offset,
            limit,
        )

    @strawberry_django.field()
    def task_by_id(self, id: uuid.UUID) -> Optional[Task]:
        return TaskModel.objects.get(id=id)

    @strawberry_django.field()
    def recommended_tasks(self, info, offset: int = 0, limit: int = 5) -> Paged[Task]:
        current_user = info.context.request.user
        if not current_user or current_user.is_anonymous:
            return Paged.of(TaskModel.objects.order_by("-created"), offset, limit)

        skills = list(current_user.profile.skills.all())
        whens = []

        locations_match = Q(geolocation__within=current_user.profile.geolocation)

        if skills and current_user.profile.geolocation:
            whens.append(When(Q(skills__in=skills) & (locations_match | Q(location_type="REMOTE")), then=Value(10)))
        if skills:
            whens.append(When(skills__in=skills, then=Value(20)))
        if current_user.profile.geolocation:
            whens.append(When(locations_match, then=Value(30)))
        return Paged.of(
            TaskModel.objects.annotate(
                custom_order=Case(
                    *whens,
                    default=Value(100),
                    output_field=IntegerField(),
                )
            )
            .distinct()
            .order_by("custom_order", "-created"),
            offset,
            limit,
        )

    @strawberry_django.field()
    def collaboration_tools(
        self, info: Info, space_id: uuid.UUID, offset: int = 0, limit: int = 10
    ) -> Paged[CollaborationTool]:
        user: UserModel = info.context.request.user
        if user.is_anonymous or not user.is_member_of_community_with_id(space_id):
            raise PermissionDenied("Forbidden")

        return Paged.of(
            CollaborationToolModel.objects.filter(community__id=space_id).order_by("-created_at"),
            offset,
            limit,
        )

    @strawberry_django.field()
    def spaces_by_name(self, info, substring: str, offset: int = 0, limit: int = 5) -> Paged[Space]:
        string_not_empty(substring)

        title_query = IContains(
            F("title"),
            substring,
        )

        return Paged.of(
            CommunityModel.objects.annotate(member_count=Count("memberships"))
            .filter(title_query)
            # Bug HOLI-6780: added created as second order criterion for deterministic order.
            # This still has wrong order if while paging the membership counts change. Signed off by Max.
            .order_by("-member_count", "-created"),
            offset,
            limit,
        )
