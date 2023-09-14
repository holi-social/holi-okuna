import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from typing import List, Optional

import requests
import strawberry
import structlog
from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.contrib.gis import geos
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q, Value
from django.db.models.functions import Concat
from django.db.models.lookups import IContains
from django.utils.translation import gettext_lazy as _
from graphql import GraphQLError
from rest_framework.exceptions import ValidationError
from strawberry.file_uploads import Upload
from strawberry.types import ExecutionContext, Info
from strawberry_django_plus import gql
from strawberry_django_plus.optimizer import DjangoOptimizerExtension
from typing_extensions import Annotated

from openbook.graphql_errors import GraphQLErrorCodes
from openbook.graphql_types import (
    SDG,
    AppVersionResponse,
    CollaborationTool,
    CollectionType,
    ContentType,
    DiscoverSpaces,
    ExternalLink,
    FeatureToggle,
    GeoJSON,
    GeoJSONInput,
    Insight,
    MySpaces,
    Notification,
    Paged,
    Post,
    PostComment,
    ReactionAction,
    Skill,
    Space,
    SpaceUserConnectionType,
    Task,
    Topic,
    UpdateConnectionAction,
    User,
)
from openbook.helpers import (
    publish_space_created_event,
    publish_space_deleted_event,
    publish_space_user_added_event,
    publish_space_user_left_event,
    publish_space_user_removed_event,
    publish_user_deleted_event,
    publish_user_name_updated_event,
)
from openbook.middleware.graphql_error_extension import GraphQLErrorExtension
from openbook.settings.sentry_config import HoliSentryTracingExtension
from openbook.utils import (
    invalidate_discover_spaces_query_cache,
)
from openbook_auth.models import User as UserModel
from openbook_auth.models import UserBlock as UserBlockModel
from openbook_auth.models import UserConnectionStatus
from openbook_auth.serializers.authenticated_user_serializers import (
    UpdateAuthenticatedUserSerializer,
)
from openbook_auth.tasks import update_ory_user_identity, update_ory_user_names
from openbook_auth.validators import string_not_empty
from openbook_common.helpers import is_parameter_null
from openbook_common.models import AppVersion as AppVersionModel
from openbook_common.models import FeatureToggle as FeatureToggleModel
from openbook_common.types import GeolocationFeature, NeedUpdateType, ReactionType
from openbook_common.utils.helpers import is_uuid
from openbook_communities.models import CollaborationTool as CollaborationToolModel
from openbook_communities.models import Community as CommunityModel
from openbook_communities.models import ExternalLinkType
from openbook_communities.models import Task as TaskModel
from openbook_communities.models import VisibilityType
from openbook_communities.serializers.communities_serializers import (
    AddCollaborationToolSerializer,
    AddExternalLinkSerializer,
    CreateCommunitySerializer,
    CreateTaskSerializer,
    InviteToCommunityByEmailSerializer,
    UpdateCollaborationToolSerializer,
    UpdateCommunitySerializer,
    UpdateExternalLinkSerializer,
    UpdateTaskSerializer,
    ValidateCommunitySerializer,
)
from openbook_communities.serializers.community_serializers import (
    CommunityUserConnectionSerializer,
)
from openbook_connections.serializers import UpdateConnectionWithUserSerializer
from openbook_insights.models import Insight as InsightModel
from openbook_moderation.models import ModeratedObject as ModeratedObjectModel
from openbook_notifications.models import Notification as NotificationModel
from openbook_posts.models import Post as PostModel
from openbook_posts.models import PostComment as PostCommentModel
from openbook_posts.serializers.post_comments_serializers import CommentPostSerializer
from openbook_posts.serializers.post_serializers import EditCommunityPostSerializer
from openbook_posts.serializers.posts_serializers import CreateCommunityPostSerializer
from openbook_terms.models import SDG as SDGModel
from openbook_terms.models import Skill as SkillModel
from openbook_terms.models import Topic as TopicModel

PUBLISHED_NOTIFICATION_TYPES = [
    NotificationModel.CONNECTION_REQUEST,
    NotificationModel.CONNECTION_ACCEPTED,
    NotificationModel.CONNECTION_CONFIRMED,
    NotificationModel.COMMUNITY_MEMBERSHIP_REQUEST,
    NotificationModel.COMMUNITY_MEMBERSHIP_APPROVED,
    NotificationModel.COMMUNITY_MEMBERSHIP_REVOKED,
    NotificationModel.COMMUNITY_ADMIN_PRIVILEGES_GRANTED,
    NotificationModel.COMMUNITY_ADMIN_PRIVILEGES_REVOKED,
    NotificationModel.COMMUNITY_NEW_POST,
    NotificationModel.COMMUNITY_INVITE,
    NotificationModel.COMMUNITY_INVITE_DECLINED,
    NotificationModel.POST_COMMENT_USER_MENTION,
    NotificationModel.RELEASE_INFO,
]

logger = structlog.get_logger(__name__)


def get_id_spaces_count_map(query):
    with_num_spaces = list(query)
    id_to_num_spaces = {}
    for s in with_num_spaces:
        id_to_num_spaces[s.id] = s.num_spaces
    return id_to_num_spaces


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


@gql.type
class NewNotificationsResponse:
    id: Optional[uuid.UUID]
    status: bool


def resolve_post(current_user, post_id):
    try:
        return (
            PostModel.objects.filter(PostModel.is_visible_query(current_user))
            .filter(UserBlockModel.not_blocked_query(current_user, "creator"))
            .get(id=post_id)
        )
    except PostModel.DoesNotExist:
        raise GraphQLError("Post not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})


def verify_authorized_user(info):
    current_user: UserModel = info.context.request.user
    if not current_user or current_user.is_anonymous:
        raise GraphQLError("Unauthorized", extensions={"code": GraphQLErrorCodes.UNAUTHORIZED})
    return current_user


@gql.type
class Query:
    @gql.django.field
    def authenticated_user(self, info) -> Optional[User]:
        current_user = info.context.request.user
        return None if current_user.is_anonymous else current_user

    @gql.django.field
    def user_by_id(self, info, id: uuid.UUID) -> Optional[User]:
        try:
            current_user = info.context.request.user
            return UserModel.objects.filter(UserModel.is_visible_query(current_user)).get(username=id)
        except UserModel.DoesNotExist:
            raise GraphQLError("User not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

    @gql.django.field
    async def users_by_chat_identities(
        self, info, identities: List[str], offset: int = 0, limit: int = 10
    ) -> Paged[User]:
        current_user = verify_authorized_user(info)

        users = UserModel.objects.filter(Q(identity__in=identities) & UserModel.is_visible_query(current_user))

        return await Paged.aof(users, offset, limit)

    @gql.django.field
    def user_by_name(self, info, substring: str, offset: int = 0, limit: int = 5) -> Paged[User]:
        string_not_empty(substring)

        current_user = info.context.request.user
        users_to_exclude_ids = [current_user.id] if not current_user.is_anonymous else []
        excludes_filter = ~Q(id__in=users_to_exclude_ids) & UserModel.is_visible_query(current_user)
        full_name_query = (
            IContains(
                Concat(F("profile__name"), Value(" "), F("profile__last_name")),
                substring,
            )
            & excludes_filter
        )

        total_results = UserModel.objects.filter(full_name_query).count()

        by_first_name_query = (
            UserModel.objects.select_related("profile")
            .filter(Q(profile__name__icontains=substring) & excludes_filter)
            .order_by("profile__name", "profile__last_name")
        )
        by_first_name = list(by_first_name_query[offset : offset + limit])
        by_first_name_len = len(by_first_name)

        if by_first_name_len >= limit:
            return Paged(by_first_name, total_results)

        if by_first_name_len > 0:
            new_offset = 0
            new_limit = limit - by_first_name_len
        else:
            new_offset = offset - by_first_name_query.count()
            new_limit = limit

        by_full_name = list(
            UserModel.objects.select_related("profile")
            .filter(full_name_query & ~Q(profile__name__icontains=substring))
            .order_by("profile__name", "profile__last_name")[new_offset : new_offset + new_limit]
        )
        return Paged(by_first_name + by_full_name, total_results)

    @gql.django.field
    def user_suggestions(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user
        query = (
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_query(current_user))
            .filter(date_joined__lte=datetime.now() - timedelta(hours=1))
            .order_by("-date_joined")
        )
        if current_user.id:
            query = query.exclude(id=current_user.id)
        return Paged.of(
            query,
            offset,
            limit,
        )

    @gql.django.field
    def check_app_version(self, version: str, build_number: str) -> AppVersionResponse:
        try:
            app_version = AppVersionModel.objects.filter(version=version, build_number=build_number)
            if app_version.exists():
                return app_version.first()
            app_version = AppVersionModel.objects.get(version=version, build_number__isnull=True)
        except AppVersionModel.DoesNotExist:
            logger.info(f"App version {version} not found. Creating a new App Version.")
            return AppVersionModel.objects.create(version=version)
        return app_version

    @gql.django.field
    async def feature_toggles(self) -> List[FeatureToggle]:
        return FeatureToggleModel.objects.all()

    @gql.django.field
    def insights_by_user_id(self, info, id: uuid.UUID, offset: int = 0, limit: int = 10) -> Paged[Insight]:
        current_user = info.context.request.user
        try:
            user = UserModel.objects.filter(UserModel.is_visible_query(current_user)).get(username=id)
        except UserModel.DoesNotExist:
            raise GraphQLError("User not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
        return Paged.of(
            InsightModel.objects.filter(creator=user).order_by("-date_published", "id"),
            offset,
            limit,
        )

    @gql.django.field
    @sync_to_async
    def last_insights(self, info, offset: int = 0, limit: int = 10) -> Paged[Insight]:
        current_user = info.context.request.user
        paged_insights = Paged.of(
            InsightModel.objects.filter(
                Q(creator__isnull=True) | UserModel.is_visible_ignore_blocked_query(current_user, "creator"),
                date_published__lte=datetime.now(),
            )
            .select_related("creator", "creator__profile", "topic")
            .prefetch_related(
                "posts",
                "posts__creator",
                "posts__comments__commenter",
            )
            .order_by("-date_published", "id")
            .cache(ops=["fetch", "count"], timeout=300),
            offset,
            limit,
        )

        return paged_insights

    @gql.django.field
    def insight_by_id(self, info, id: uuid.UUID) -> Optional[Insight]:
        current_user = info.context.request.user
        try:
            return (
                InsightModel.objects.filter(
                    Q(creator__isnull=True) | UserModel.is_visible_query(current_user, "creator")
                )
                .filter(date_published__lte=datetime.now())
                .get(id=id)
            )
        except InsightModel.DoesNotExist:
            raise GraphQLError("Insight not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

    @gql.django.field
    def post_by_id(self, info, id: uuid.UUID) -> Optional[Post]:
        return resolve_post(info.context.request.user, id)

    @gql.django.field
    def topics(self, offset: int = 0, limit: int = 50) -> Paged[Topic]:
        return Paged.of(TopicModel.objects.all().order_by("title"), offset, limit)

    @gql.django.field
    def sdgs(self, offset: int = 0, limit: int = 50) -> Paged[SDG]:
        return Paged.of(SDGModel.objects.all().order_by("number"), offset, limit)

    @gql.django.field
    def skills(self, offset: int = 0, limit: int = 50) -> Paged[Skill]:
        return Paged.of(SkillModel.objects.all().order_by("title"), offset, limit)

    @gql.django.field
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
        skill_slugs: Optional[List[Optional[str]]] = None,
        member_id: Optional[uuid.UUID] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[Space]:
        return spaces_for_filter(
            offset,
            limit,
            topic_id,
            geolocation,
            skill_ids,
            topic_slug,
            skill_slugs,
            member_id,
        )

    @gql.django.field
    @sync_to_async
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

    @gql.django.field
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

    @gql.django.field
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
                .aget(query)
            )
        except CommunityModel.DoesNotExist:
            raise GraphQLError("Space not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

    @gql.django.field
    def tasks_by_space_id(self, space_id: uuid.UUID, offset: int = 0, limit: int = 10) -> Paged[Task]:
        return Paged.of(
            TaskModel.objects.filter(community__id=space_id).order_by("-created"),
            offset,
            limit,
        )

    @gql.django.field
    def task_by_id(self, id: uuid.UUID) -> Optional[Task]:
        try:
            return TaskModel.objects.get(id=id)
        except TaskModel.DoesNotExist:
            raise GraphQLError("Task not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

    @gql.django.field
    def notifications(self, info, offset: int = 0, limit: int = 10) -> Paged[Notification]:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            return Paged()
        return Paged.of(
            NotificationModel.objects.filter(
                owner=current_user,
                notification_type__in=PUBLISHED_NOTIFICATION_TYPES,
            ).order_by("-created"),
            offset,
            limit,
        )

    @gql.django.field
    def has_new_notifications(self, info) -> NewNotificationsResponse:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            return NewNotificationsResponse(id=None, status=False)

        notifications = NotificationModel.objects.filter(
            owner=current_user, notification_type__in=PUBLISHED_NOTIFICATION_TYPES
        )
        if current_user.last_seen_notification_timestamp:
            notifications = notifications.filter(created__gt=current_user.last_seen_notification_timestamp)

        return NewNotificationsResponse(id=current_user.username, status=notifications.exists())

    @gql.django.field
    def collaboration_tools(self, space_id: uuid.UUID, offset: int = 0, limit: int = 10) -> Paged[CollaborationTool]:
        return Paged.of(
            CollaborationToolModel.objects.filter(community__id=space_id).order_by("-created_at"),
            offset,
            limit,
        )


def to_input_dict(input):
    """
    converts a strawberry input object to a dict without null values, so it can be validated
    """
    return {k: v for k, v in strawberry.asdict(input).items() if v != strawberry.UNSET}


@gql.input
class GeolocationPointInput:
    latitude: float
    longitude: float

    @staticmethod
    def to_point(geolocation_input):
        if geolocation_input is None:
            return None

        longitude = float(geolocation_input.get("longitude"))
        latitude = float(geolocation_input.get("latitude"))
        return geos.Point(longitude, latitude, srid=4326)


@gql.input
class OnboardingStepInput:
    text: str


@gql.input
class UpdateAuthenticatedUserInput:
    avatar: Optional[Upload] = strawberry.UNSET
    first_name: Optional[str] = strawberry.UNSET
    last_name: Optional[str] = strawberry.UNSET
    about_me: Optional[str] = strawberry.UNSET
    pronouns: Optional[str] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeoJSONInput] = strawberry.UNSET
    engagement_level: Optional[str] = strawberry.UNSET
    interests: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    sdgs: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    skills: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET


@gql.input
class UpdateConnectionWithUserInput:
    user_id: Optional[str] = strawberry.UNSET
    action: UpdateConnectionAction


@gql.input
class CreatePostCommentInput:
    post_id: uuid.UUID
    text: str


@gql.type
class CreatePostCommentOutput:
    post_comment: PostComment
    post_by_id: Post


@gql.input
class ValidateSpaceInput:
    title: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    topics: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    cover: Optional[Upload] = strawberry.UNSET
    sdgs: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET


@gql.input
class CreateSpaceInput:
    title: str
    description: str
    topics: List[Optional[uuid.UUID]]
    cover: Upload


@gql.input
class UpdateSpaceInput:
    id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    topics: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    cover: Optional[Upload] = strawberry.UNSET
    avatar: Optional[Upload] = strawberry.UNSET
    sdgs: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    contact_description: Optional[str] = strawberry.UNSET
    contact_email: Optional[str] = strawberry.UNSET
    contact_phone: Optional[str] = strawberry.UNSET
    onboarding_steps: Optional[List[Optional[OnboardingStepInput]]] = strawberry.UNSET


@gql.input
class CreatePostInput:
    space_id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    text: str
    image: Optional[Upload] = strawberry.UNSET
    visibility: VisibilityType


@gql.input
class UpdatePostInput:
    post_id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    text: Optional[str] = strawberry.UNSET
    image: Optional[Upload] = strawberry.UNSET
    visibility: Optional[VisibilityType] = strawberry.UNSET


@gql.input
class CreateTaskInput:
    space_id: uuid.UUID
    name: str
    description: str
    visibility: VisibilityType
    location_type: TaskModel.LocationType
    regularity: TaskModel.Regularity
    contact_email: str
    slots_available: Optional[int] = strawberry.UNSET
    thumbnail: Optional[Upload] = strawberry.UNSET
    skills: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    contact_phone: Optional[str] = strawberry.UNSET


@gql.input
class UpdateTaskInput:
    task_id: uuid.UUID
    space_id: uuid.UUID
    name: str
    description: str
    visibility: VisibilityType
    location_type: TaskModel.LocationType
    regularity: TaskModel.Regularity
    contact_email: str
    slots_available: Optional[int] = strawberry.UNSET
    thumbnail: Optional[Upload] = strawberry.UNSET
    skills: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    contact_phone: Optional[str] = strawberry.UNSET


@gql.input
class AddCollaborationToolInput:
    space_id: uuid.UUID
    url: str
    title: str
    description: Optional[str] = strawberry.UNSET
    collection_type: CollectionType
    thumbnail: Optional[Upload] = strawberry.UNSET


@gql.input
class UpdateCollaborationToolInput:
    id: uuid.UUID
    url: Optional[str] = strawberry.UNSET
    title: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    collection_type: Optional[CollectionType] = strawberry.UNSET
    thumbnail: Optional[Upload] = strawberry.UNSET


@gql.input
class AddExternalLinkInput:
    space_id: uuid.UUID
    url: str
    type: ExternalLinkType
    name: str


@gql.input
class UpdateExternalLinkInput:
    id: uuid.UUID
    url: Optional[str] = strawberry.UNSET
    type: Optional[ExternalLinkType] = strawberry.UNSET
    name: Optional[str] = strawberry.UNSET


@gql.type
class Result:
    success: bool


@gql.type
class Mutation:
    @gql.mutation
    @sync_to_async
    def update_authenticated_user(self, info, input: UpdateAuthenticatedUserInput) -> User:
        current_user = verify_authorized_user(info)

        l = [1, 2, 3]
        l[5]

        input_dict = to_input_dict(input)
        if input.first_name:
            input_dict["name"] = input.first_name

        # TODO: Only for temporary backwards compatibility, remove in HOLI-4353
        if input.geolocation and "properties" not in input.geolocation:
            input_dict.pop("geolocation")

        serializer = UpdateAuthenticatedUserSerializer(data=input_dict)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        remove_avatar = is_parameter_null(data, "avatar")

        current_user.update(
            name=data.get("name"),
            last_name=data.get("last_name"),
            about_me=data.get("about_me"),
            pronouns=data.get("pronouns"),
            location=data.get("location"),
            geolocation=data.get("geolocation"),
            update_location=input.location is not strawberry.UNSET or input.geolocation is not strawberry.UNSET,
            engagement_level=data.get("engagement_level"),
            interests=data.get("interests"),
            sdgs=data.get("sdgs"),
            skills=data.get("skills"),
            avatar=data.get("avatar"),
            remove_avatar=remove_avatar,
            save=True,
        )

        if input.first_name or input.last_name:
            update_ory_user_names(current_user.id)
            publish_user_name_updated_event(user=current_user)

        # set identity when needed
        if not current_user.identity and input.first_name:
            current_user.identity = UserModel.sanitize_identity_input(input.first_name)

            if (
                UserModel.is_invalid_identity(current_user.identity)
                or UserModel.is_identity_taken(current_user.identity)
                or not update_ory_user_identity(current_user)
            ):
                identity_wish = UserModel.sanitize_identity_input(current_user.profile.full_name())
                # when the user has no last name, full_name is identical to first_name, so init the counter with 0
                # to already start adding a number on the call to next_unique_identity.
                # Otherwise init with None, to not add a number on the first call to next_unique_identity
                counter = None if identity_wish != current_user.identity else 0
                tries = 0
                taken_identities = UserModel.get_taken_identities(identity_wish)
                while True:
                    current_user.identity, counter = UserModel.next_unique_identity(
                        identity_wish, taken_identities, counter
                    )
                    if update_ory_user_identity(current_user):
                        break  # Ory update was successful, and there was no collision. We are done.
                    tries += 1
                    if tries > 10:
                        logger.error("Could not generate identity from user name after %s attempts.", tries)
                        raise ValidationError({"identity": _("Could not generate identity from user names.")})

            current_user.save()

        cache.set(f"{settings.USER_CACHE_PREFIX}{current_user.username}", current_user, timeout=300)

        return current_user

    @gql.mutation
    @sync_to_async
    def update_connection_with_user(self, info, input: UpdateConnectionWithUserInput) -> User:
        current_user = verify_authorized_user(info)

        serializer = UpdateConnectionWithUserSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_to_connect_to = current_user.get_user_with_username(username=data.get("user_id"))

        current_connection_status = current_user.get_connection_status_with_user_id(user_id=user_to_connect_to.id)

        # Connect action
        if input.action == UpdateConnectionAction.CONNECT:
            # if current user needs to confirm connection, run confirm_connection_with_user_with_id
            if current_connection_status == UserConnectionStatus.PENDING_CONFIRMATION:
                current_user.confirm_connection_with_user_with_id(user_id=user_to_connect_to.id)

            # if there is no connection yet (no requests or pending confirmation), run connect_with_user_with_id
            if current_connection_status == UserConnectionStatus.NOT_CONNECTED:
                current_user.connect_with_user_with_id(user_id=user_to_connect_to.id)

        # Disconnect action (only run if current connection status is different than NOT_CONNECTED)
        elif (
            input.action == UpdateConnectionAction.DISCONNECT
            and current_connection_status != UserConnectionStatus.NOT_CONNECTED
        ):
            current_user.disconnect_from_user_with_id(user_id=user_to_connect_to.id)

        return user_to_connect_to

    @gql.mutation
    @sync_to_async
    def update_post_comment(self, info, input: CreatePostCommentInput) -> CreatePostCommentOutput:
        current_user = verify_authorized_user(info)

        serializer = CommentPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comment_text = data.get("text")
        post_id = data.get("post_id")

        with transaction.atomic():
            post_comment = current_user.comment_post_with_id(post_id=post_id, text=comment_text)

        return CreatePostCommentOutput(post_comment=post_comment, post_by_id=resolve_post(current_user, post_id))

    @gql.mutation
    @sync_to_async
    def delete_post_comment(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        current_user.delete_comment_with_id(post_comment_id=id)

        return Result(success=True)

    @gql.mutation(description="When no userId is provided, the logged in user is used instead.")
    @sync_to_async
    def update_space_user_connection(
        self,
        info,
        space_id: uuid.UUID,
        connection_type: SpaceUserConnectionType,
        connect_action: UpdateConnectionAction,
        user_id: Optional[uuid.UUID] = None,
        message: Optional[str] = None,
    ) -> Space:
        current_user = verify_authorized_user(info)

        serializer = CommunityUserConnectionSerializer(data={"community_id": space_id, "message": message})
        serializer.is_valid(raise_exception=True)

        space = CommunityModel.objects.get(id=space_id)

        cT = SpaceUserConnectionType
        a = UpdateConnectionAction

        invalidate_discover_spaces_query_cache()

        if not user_id or current_user.username == user_id:
            # perform for current user
            match (connection_type, connect_action):
                case (cT.MEMBERSHIP_REQUESTOR, a.CONNECT):
                    return current_user.request_membership_to_community_with_name(space.name, message)
                case (cT.MEMBERSHIP_REQUESTOR, a.DISCONNECT):
                    return current_user.revoke_membership_request_to_community_with_name(space.name)
                case (cT.MEMBERSHIP_INVITEE, a.CONNECT):
                    space = current_user.accept_membership_invite_to_community_for_username(space.name)
                    publish_space_user_added_event(username=str(current_user.username), community=space)
                    return space
                case (cT.MEMBERSHIP_INVITEE, a.DISCONNECT):
                    return current_user.reject_membership_invite_to_community_for_username(space.name)
                case (cT.FOLLOWER, a.CONNECT):
                    return current_user.enable_new_post_notifications_for_community_with_name(space.name)
                case (cT.FOLLOWER, a.DISCONNECT):
                    return current_user.disable_new_post_notifications_for_community_with_name(space.name)
                case (cT.MEMBER | cT.ADMINISTRATOR, a.LEAVE_SPACE):
                    community_to_leave = current_user.leave_community_with_name(space.name)
                    publish_space_user_left_event(user=current_user, community=community_to_leave)
                    return community_to_leave
                case _:
                    raise GraphQLError("Operation not allowed", extensions={"code": GraphQLErrorCodes.FORBIDDEN})
        else:
            # perform for other user
            match (connection_type, connect_action):
                case (cT.MEMBERSHIP_REQUESTOR, a.DISCONNECT):
                    return current_user.revoke_membership_request_to_community_for_username(user_id, space.name)
                case (cT.MEMBER, a.CONNECT):
                    space = current_user.approve_membership_request_to_community_for_username(user_id, space.name)
                    publish_space_user_added_event(username=str(user_id), community=space)
                    return space
                case (cT.MEMBERSHIP_INVITEE, a.CONNECT):
                    return current_user.invite_to_community(username=str(user_id), community=space)
                case (cT.ADMINISTRATOR, a.GRANT_ADMIN_ACCESS):
                    return current_user.add_administrator_with_username_to_community_with_name(user_id, space.name)
                case (cT.ADMINISTRATOR, a.REVOKE_ADMIN_ACCESS):
                    return current_user.remove_administrator_with_username_from_community_with_name(
                        user_id, space.name
                    )
                case (cT.ADMINISTRATOR, a.REMOVE_MEMBER):
                    community = current_user.remove_member_from_community(user_id, space.name)
                    user_to_remove = UserModel.objects.get(username=user_id)
                    publish_space_user_removed_event(user=user_to_remove, community=community)
                    return community
                case _:
                    raise GraphQLError(
                        "Operation not allowed",
                        extensions={"code": GraphQLErrorCodes.FORBIDDEN},
                    )

    @gql.mutation(
        deprecation_reason="Changed return type to reflect created entity, use create_space_post_2. Deprecated since v1.1.0"
    )
    @sync_to_async
    def create_space_post(self, info: Info, input: CreatePostInput) -> Space:
        current_user = verify_authorized_user(info)

        serializer = CreateCommunityPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        current_user.create_community_post(**data)

        return CommunityModel.objects.get(id=data.get("space_id"))

    @gql.mutation
    @sync_to_async
    def create_space_post_2(self, info: Info, input: CreatePostInput) -> Post:
        current_user = verify_authorized_user(info)

        serializer = CreateCommunityPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.create_community_post(**data)

    @gql.mutation
    @sync_to_async
    def update_space_post(self, info: Info, input: UpdatePostInput) -> Post:
        current_user = verify_authorized_user(info)

        serializer = EditCommunityPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        data["remove_image"] = is_parameter_null(data, "image")

        return current_user.update_community_post(**data)

    @gql.mutation
    @sync_to_async
    def delete_space_post(self, info: Info, id: uuid.UUID) -> Space:
        current_user = verify_authorized_user(info)

        post = PostModel.objects.get(id=id)
        current_user.delete_post(post)

        return post.community

    @gql.mutation
    @sync_to_async
    def delete_authenticated_user(self, info) -> Result:
        current_user = verify_authorized_user(info)
        headers = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}
        logger.info(f"Deleting user {current_user.username}...")

        response = requests.delete(
            f"{settings.ORY_BASE_URL}/admin/identities/{current_user.username}",
            headers=headers,
        )
        # Ory returns 204 in case of success
        if not response.ok:
            error_message = response.error.error if response.error else "Unknown"
            raise Exception(f"Deleting user {current_user.username} in ory failed: {error_message}")

        # crude hack to prevent concurrent user references (e.g. mentions in comments) to let the user deletion fail
        # we just retry a couple of times
        for count in range(3, -1, -1):
            try:
                exclusive_administrated_communities = list(current_user.get_exclusive_administrated_communities())

                current_user.delete()
                publish_user_deleted_event(user=current_user)
                logger.info(f"Successfully deleted user {current_user.username}")

                logger.warning(f"All spaces exclusively administered by {current_user.username} will be deleted")

                if exclusive_administrated_communities:
                    for space in exclusive_administrated_communities:
                        # Make a copy of the space before deleting it to pass it as a SpaceDeleted event payload
                        space_to_delete = deepcopy(space)
                        space.delete()
                        publish_space_deleted_event(space_to_delete)

                    invalidate_discover_spaces_query_cache()

                return Result(success=True)
            except (Exception,):
                logger.warning(
                    f"Could not delete user with id {current_user.username}, retrying #{count} more times",
                    exc_info=True,
                )
                if count == 0:
                    logger.exception(
                        f"Could not delete user with id {current_user.username}, no more retries, failing"
                    )
                    raise GraphQLError(
                        "Unable to delete user in okuna",
                        extensions={"code": GraphQLErrorCodes.INTERNAL_SERVER_ERROR},
                    )

    @gql.mutation
    @sync_to_async
    def report_content(
        self,
        info,
        object_id: uuid.UUID,
        content_type: ContentType,
        description: Optional[str] = None,
    ) -> Result:
        current_user = verify_authorized_user(info)

        # hardcoded category_id to block user content. Needs to be imported via fixture!
        category_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        match content_type:
            case ContentType.POST:
                current_user.report_post_with_id(object_id, category_id, description)
            case ContentType.POST_COMMENT:
                current_user.report_comment_with_id(object_id, category_id, description)
            case ContentType.USER:
                current_user.report_user_with_username(str(object_id), category_id, description)
            case ContentType.SPACE:
                current_user.report_community_with_id(object_id, category_id, description)
            case _:
                raise GraphQLError(
                    f"Unknown ContentType {content_type.value}",
                    extensions={"code": GraphQLErrorCodes.FORBIDDEN},
                )

        return Result(success=True)

    @gql.mutation
    @sync_to_async
    def block_user(self, info, user_id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)
        username_of_user_to_block = str(user_id)

        current_user.block_user_with_username(username_of_user_to_block)

        return Result(success=True)

    @gql.mutation
    @sync_to_async
    def validate_space(self, info, input: ValidateSpaceInput) -> Result:
        verify_authorized_user(info)

        serializer = ValidateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)

        return Result(success=True)

    @gql.mutation
    @sync_to_async
    def create_space(self, info, input: CreateSpaceInput) -> Space:
        current_user = verify_authorized_user(info)

        serializer = CreateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        community = current_user.create_community(
            title=data.get("title"),
            type=CommunityModel.COMMUNITY_TYPE_PUBLIC,
            description=data.get("description"),
            cover=data.get("cover"),
            invites_enabled=True,
            topic_ids=data.get("topics"),
        )

        publish_space_created_event(community=community)
        invalidate_discover_spaces_query_cache()

        return community

    @gql.mutation
    @sync_to_async
    def update_space(self, info, input: UpdateSpaceInput) -> Space:
        current_user = verify_authorized_user(info)

        serializer = UpdateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        space = current_user.update_community_with_id(
            community_id=data.get("id"),
            title=data.get("title"),
            description=data.get("description"),
            topic_ids=data.get("topics"),
            cover=data.get("cover"),
            remove_cover=is_parameter_null(data, "cover"),
            avatar=data.get("avatar"),
            remove_avatar=is_parameter_null(data, "avatar"),
            sdg_ids=data.get("sdgs"),
            location=data.get("location"),
            geolocation=(GeolocationPointInput.to_point(data.get("geolocation"))),
            contact_description=data.get("contact_description"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            onboarding_steps=data.get("onboarding_steps"),
        )

        invalidate_discover_spaces_query_cache()

        return space

    @gql.mutation
    @sync_to_async
    def delete_space(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)
        space = CommunityModel.objects.get(id=id)

        with transaction.atomic():
            current_user.delete_community_with_id(
                community_id=id,
            )

        publish_space_deleted_event(space)

        invalidate_discover_spaces_query_cache()

        return Result(success=True)

    @gql.mutation
    @sync_to_async
    def invite_to_space_by_email(self, info, email: str, space_id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)
        current_user_language = info.context.request.META.get("HTTP_ACCEPT_LANGUAGE")

        serializer = InviteToCommunityByEmailSerializer(data={"email": email, "space_id": space_id})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        current_user.invite_to_community_by_email(
            email=data.get("email"), space_id=data.get("space_id"), language=current_user_language
        )

        return Result(success=True)

    @gql.mutation
    @sync_to_async
    def create_task(self, info, input: CreateTaskInput) -> Task:
        current_user = verify_authorized_user(info)

        serializer = CreateTaskSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return current_user.create_task(
            space_id=data.get("space_id"),
            name=data.get("name"),
            description=data.get("description"),
            slots_available=data.get("slots_available"),
            visibility=data.get("visibility"),
            location_type=data.get("location_type"),
            location=data.get("location"),
            geolocation=(GeolocationPointInput.to_point(data.get("geolocation"))),
            regularity=data.get("regularity"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            skills=data.get("skills"),
            thumbnail=data.get("thumbnail"),
        )

    @gql.mutation
    @sync_to_async
    def update_task(self, info, input: UpdateTaskInput) -> Task:
        current_user = verify_authorized_user(info)

        serializer = UpdateTaskSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.update_task(
            task_id=data.get("task_id"),
            space_id=data.get("space_id"),
            name=data.get("name"),
            description=data.get("description"),
            slots_available=data.get("slots_available"),
            visibility=data.get("visibility"),
            location_type=data.get("location_type"),
            location=data.get("location"),
            geolocation=(GeolocationPointInput.to_point(data.get("geolocation"))),
            regularity=data.get("regularity"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            skills=data.get("skills"),
            thumbnail=data.get("thumbnail"),
            remove_thumbnail=is_parameter_null(data, "thumbnail"),
        )

    @gql.mutation
    @sync_to_async
    def delete_task(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            current_user.delete_task_with_id(task_id=id)

        return Result(success=True)

    @gql.mutation
    @sync_to_async
    def update_post_reaction(
        self,
        info,
        id: uuid.UUID,
        reaction_type: ReactionType,
        reaction_action: ReactionAction,
    ) -> Post:
        current_user = verify_authorized_user(info)
        post = PostModel.objects.get(id=id)
        if reaction_action == ReactionAction.SET:
            post.react(current_user, reaction_type)
        else:
            post.clear_reaction(current_user, reaction_type)
        return post

    @gql.mutation
    @sync_to_async
    def update_post_comment_reaction(
        self,
        info,
        id: uuid.UUID,
        reaction_type: ReactionType,
        reaction_action: ReactionAction,
    ) -> PostComment:
        current_user = verify_authorized_user(info)
        post_comment = PostCommentModel.objects.get(id=id)
        if reaction_action == ReactionAction.SET:
            post_comment.react(current_user, reaction_type)
        else:
            post_comment.clear_reaction(current_user, reaction_type)
        return post_comment

    @gql.mutation
    @sync_to_async
    def last_seen_notification(self, info, notification_id: uuid.UUID) -> NewNotificationsResponse:
        current_user = verify_authorized_user(info)
        current_user.store_last_seen_notification(notification_id)

        # Update user cache in order to update the value of last_seen_notification_timestamp
        cache.set(f"{settings.USER_CACHE_PREFIX}{current_user.username}", current_user, timeout=300)

        return NewNotificationsResponse(id=current_user.username, status=False)

    @gql.mutation
    @sync_to_async
    def add_collaboration_tool(self, info, input: AddCollaborationToolInput) -> CollaborationTool:
        current_user = verify_authorized_user(info)

        serializer = AddCollaborationToolSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.add_collaboration_tool(
            space_id=data.get("space_id"),
            url=data.get("url"),
            title=data.get("title"),
            description=data.get("description"),
            collection_type=data.get("collection_type"),
            thumbnail=data.get("thumbnail"),
        )

    @gql.mutation
    @sync_to_async
    def update_collaboration_tool(self, info, input: UpdateCollaborationToolInput) -> CollaborationTool:
        current_user = verify_authorized_user(info)

        serializer = UpdateCollaborationToolSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.update_collaboration_tool(
            collaboration_tool_id=data.get("id"),
            url=data.get("url"),
            title=data.get("title"),
            description=data.get("description"),
            collection_type=data.get("collection_type"),
            thumbnail=data.get("thumbnail"),
            remove_thumbnail=is_parameter_null(data, "thumbnail"),
        )

    @gql.mutation
    @sync_to_async
    def delete_collaboration_tool(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            current_user.delete_collaboration_tool(
                collaboration_tool_id=id,
            )

        return Result(success=True)

    @gql.mutation
    @sync_to_async
    def add_external_link(self, info, input: AddExternalLinkInput) -> ExternalLink:
        current_user = verify_authorized_user(info)

        serializer = AddExternalLinkSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.add_external_link(
            space_id=data.get("space_id"),
            url=data.get("url"),
            type=data.get("type"),
            name=data.get("name"),
        )

    @gql.mutation
    @sync_to_async
    def update_external_link(self, info, input: UpdateExternalLinkInput) -> ExternalLink:
        current_user = verify_authorized_user(info)

        serializer = UpdateExternalLinkSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.update_external_link(
            external_link_id=data.get("id"),
            url=data.get("url"),
            type=data.get("type"),
            name=data.get("name"),
        )

    @gql.mutation
    @sync_to_async
    def delete_external_link(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            current_user.delete_external_link(
                external_link_id=id,
            )

        return Result(success=True)


class HoliSchema(strawberry.Schema):
    def process_errors(
        self,
        errors: List[GraphQLError],
        execution_context: Optional[ExecutionContext] = None,
    ) -> None:
        real_errors = [
            error
            for error in errors
            if not (
                error.extensions
                and "code" in error.extensions
                and error.extensions["code"]
                in [
                    GraphQLErrorCodes.BAD_USER_INPUT,
                    GraphQLErrorCodes.NOT_FOUND,
                    GraphQLErrorCodes.FORBIDDEN,
                    GraphQLErrorCodes.UNAUTHORIZED,
                ]
            )
        ]
        super().process_errors(real_errors, execution_context)


schema = HoliSchema(
    query=Query,
    mutation=Mutation,
    extensions=[
        DjangoOptimizerExtension,
        GraphQLErrorExtension,
        HoliSentryTracingExtension,
    ],
)
