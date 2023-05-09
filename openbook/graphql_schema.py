from collections import defaultdict
from datetime import datetime, timedelta
import json

from rest_framework.exceptions import ValidationError

import requests
import structlog
from cacheops import cached_as
from django.conf import settings
from django.core.cache import cache
from django.contrib.gis import geos
from django.db import Error, transaction
from django.db.models import Count, F, Value, Prefetch
from django.db.models.functions import Concat
from django.db.models.lookups import IContains
from django.utils.translation import gettext_lazy as _
from graphql import GraphQLError
from strawberry.file_uploads import Upload
from strawberry.types import Info
from strawberry_django_plus.optimizer import DjangoOptimizerExtension

from openbook.graphql_errors import GraphQLErrorCodes
from openbook.helpers import (
    publish_space_deleted_event,
    publish_space_user_added_event,
    publish_space_created_event,
    publish_user_name_updated_event,
)
from openbook.utils import generate_discover_spaces_hash_key, invalidate_discover_spaces_query_cache
from openbook_auth.images import delete_avatar
from openbook_auth.tasks import update_ory_user
from openbook_auth.validators import string_not_empty
from openbook_auth.views.authenticated_user.serializers import (
    UpdateAuthenticatedUserSerializer,
)

from openbook_communities.views.communities.serializers import (
    AddCollaborationToolSerializer,
    CreateCommunitySerializer,
    CreateTaskSerializer,
    UpdateTaskSerializer,
    UpdateCollaborationToolSerializer,
    UpdateCommunitySerializer,
    ValidateCommunitySerializer,
)
from openbook_connections.serializers import UpdateConnectionWithUserSerializer
from openbook_moderation.models import ModeratedObject
from openbook_posts.views.post.serializers import EditCommunityPostSerializer
from openbook_posts.views.post_comments.serializers import CommentPostSerializer
from openbook_common.utils.helpers import is_uuid
from openbook_posts.views.posts.serializers import (
    CreatePostSerializer,
    CreateCommunityPostSerializer,
)
from openbook.middleware.graphql_error_extension import GraphQLErrorExtension

from .graphql_types import *

PUBLISHED_NOTIFICATION_TYPES = [
    NotificationModel.CONNECTION_REQUEST,
    NotificationModel.CONNECTION_ACCEPTED,
    NotificationModel.CONNECTION_CONFIRMED,
    NotificationModel.COMMUNITY_MEMBERSHIP_REQUEST,
    NotificationModel.COMMUNITY_MEMBERSHIP_APPROVED,
    NotificationModel.COMMUNITY_ADMIN_PRIVILEGES_GRANTED,
    NotificationModel.COMMUNITY_ADMIN_PRIVILEGES_REVOKED,
    NotificationModel.COMMUNITY_NEW_POST,
    NotificationModel.POST_COMMENT_USER_MENTION,
    NotificationModel.RELEASE_INFO,
]

logger = structlog.getLogger(__name__)


def get_id_spaces_count_map(query):
    with_num_spaces = list(query)
    id_to_num_spaces = {}
    for s in with_num_spaces:
        id_to_num_spaces[s.id] = s.num_spaces
    return id_to_num_spaces


@cached_as(CommunityModel)
def spaces_for_filter(
    offset: int,
    limit: int,
    topic_id: Optional[uuid.UUID] = None,
    location: Optional[str] = None,
    skill_ids: Optional[List[Optional[uuid.UUID]]] = None,
    topic_slug: Optional[str] = None,
    skill_slugs: Optional[List[Optional[str]]] = None,
    member_id: Optional[uuid.UUID] = None,
):
    query = Q()
    if topic_id is not None:
        query.add(Q(topics__id__contains=topic_id), Q.AND)
    if location is not None:
        query.add(Q(location__icontains=location), Q.AND)
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
        .order_by("-member_count", "-created"),
        offset,
        limit,
    )


@gql.type
class NewNotificationsResponse:
    id: Optional[UUID]
    status: bool


def filter_spaces_by_skill_ids(location, skill_ids, limit):
    return CommunityModel.objects.raw(
        """
            select s.id, s.skill_id, s.rn 
            from openbook_terms_skill skill, (
                select octskill.skill_id, occ.*, row_number() OVER (partition by octskill.skill_id ORDER BY occ.id) AS rn
                FROM   openbook_communities_community occ, openbook_communities_task octask, openbook_communities_task_skills octskill
                where occ.id = octask.community_id and octask.id = octskill.task_id  
            ) s
            where s.skill_id = skill.id 
            and UPPER(s.location) like UPPER(%s)
            and s.rn <= %s
            and skill.id = ANY(%s)
            order by skill.id
            """,
        [f"%{location}%", limit, skill_ids],
    ).prefetch_related("memberships__user__profile")


def filter_spaces_by_topic_ids(topic_ids, limit):
    return CommunityModel.objects.raw(
        """
            select s.id, s.topic_id, s.rn
            from openbook_terms_topic t, (
                select occtopics.topic_id, occ.*, row_number() OVER (partition by occtopics.topic_id ORDER BY occ.id) AS rn
                FROM   openbook_communities_community occ, openbook_communities_community_topics occtopics
                where occtopics.community_id = occ.id 
            ) s
            where s.topic_id = t.id 
            and s.rn <= %s
            and t.id = ANY(%s)
            order by t.id
            """,
        [limit, topic_ids],
    ).prefetch_related("memberships__user__profile")


def resolve_post(current_user, post_id):
    try:
        return (
            PostModel.objects.filter(PostModel.is_visible_query(current_user))
            .filter(UserBlock.not_blocked_query(current_user, "creator"))
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

        by_first_name_query = UserModel.objects.select_related("profile").filter(
            Q(profile__name__icontains=substring) & excludes_filter
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
            UserModel.objects.select_related("profile").filter(
                full_name_query & ~Q(profile__name__icontains=substring)
            )[new_offset : new_offset + new_limit]
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
    def last_insights(self, info, offset: int = 0, limit: int = 10) -> Paged[Insight]:
        current_user = info.context.request.user
        return Paged.of(
            InsightModel.objects.filter(Q(creator__isnull=True) | UserModel.is_visible_query(current_user, "creator"))
            .filter(date_published__lte=datetime.now())
            .order_by("-date_published", "id"),
            offset,
            limit,
        )

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
        location: Optional[str] = None,
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
            location,
            skill_ids,
            topic_slug,
            skill_slugs,
            member_id,
        )

    @gql.django.field
    def discover_spaces(
        self,
        topic_ids: Optional[List[Optional[uuid.UUID]]] = None,
        location: Optional[str] = None,
        skill_ids: Optional[List[Optional[uuid.UUID]]] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> List[Optional[DiscoverSpaces]]:
        result = []

        hash_key = generate_discover_spaces_hash_key(topic_ids, location, skill_ids, offset, limit)

        # Check whether the resolver result has already been cached and return it,
        # otherwise, query the database, create the result, and cache it.
        if hash_key in cache:
            return cache.get(hash_key)
        else:
            # get all spaces by location (independent of other filters)
            if location is not None:
                result.append(
                    DiscoverSpaces(
                        location=location,
                        spaces=spaces_for_filter(
                            offset=offset,
                            limit=limit,
                            location=location,
                        ),
                    )
                )

            # get all spaces by topic (independent of other filters)
            if topic_ids is not None:
                topic_id_to_num_spaces = get_id_spaces_count_map(
                    TopicModel.objects.filter(id__in=topic_ids).annotate(num_spaces=Count("communities"))
                )

                spaces_from_db = filter_spaces_by_topic_ids(topic_ids, limit)

                spaces_map = defaultdict(list)

                for sp in spaces_from_db:
                    spaces_map[sp.topic_id].append(sp)
                for topic_id, spaces in spaces_map.items():
                    result.append(
                        DiscoverSpaces(
                            topic_id=topic_id,
                            spaces=Paged(spaces, topic_id_to_num_spaces[topic_id]),
                        )
                    )

            # get all spaces by skill_id (including location filter)
            if skill_ids is not None:
                skill_id_to_num_spaces = get_id_spaces_count_map(
                    SkillModel.objects.filter(id__in=skill_ids).annotate(num_spaces=Count("tasks__community"))
                )

                spaces_from_db = filter_spaces_by_skill_ids(location, skill_ids, limit)

                spaces_map = defaultdict(list)

                for sp in spaces_from_db:
                    spaces_map[sp.skill_id].append(sp)
                for skill_id, spaces in spaces_map.items():
                    result.append(
                        DiscoverSpaces(
                            skill_id=skill_id,
                            location=location,
                            spaces=Paged(spaces, skill_id_to_num_spaces[skill_id]),
                        )
                    )
            # Set the result to be cached for future calls until the cache key expires after the default TTL.
            cache.set(hash_key, result)
            return result

    @gql.django.field
    def my_spaces(self, info) -> List[Optional[MySpaces]]:
        current_user = verify_authorized_user(info)

        created_spaces = MySpaces(section=_("Created"), type=SpaceUserConnectionType.CREATOR)
        created_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
            .filter(creator=current_user)
            .annotate(member_count=Count("memberships"))
            .order_by("-member_count", "-created")
        )
        member_spaces = MySpaces(section=_("Joined"), type=SpaceUserConnectionType.MEMBER)
        member_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships__user__profile")
            .filter(Q(memberships__user=current_user), ~Q(creator=current_user))
            .annotate(member_count=Count("memberships"))
            .order_by("-member_count", "-created")
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
            .annotate(member_count=Count("memberships"))
            .order_by("-member_count", "-created")
        )
        return list(
            filter(
                lambda x: x.query.count() > 0,
                [created_spaces, member_spaces, followed_spaces],
            )
        )

    @gql.django.field(
        description="idOrName can either be the space id or name (slug). If none of them is found, an error with the message 'Space not found' is thrown."
    )
    def space_by_id(self, info, id_or_name: str) -> Optional[Space]:
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
                    ModeratedObject.not_moderated_query(
                        info.context.request.user, ModeratedObject.OBJECT_TYPE_COMMUNITY
                    )
                )
                .get(query)
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
class GeolocationInput:
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
class UpdateAuthenticatedUserInput:
    avatar: Optional[Upload] = strawberry.UNSET
    first_name: Optional[str] = strawberry.UNSET
    last_name: Optional[str] = strawberry.UNSET
    about_me: Optional[str] = strawberry.UNSET
    pronouns: Optional[str] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationInput] = strawberry.UNSET
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
    geolocation: Optional[GeolocationInput] = strawberry.UNSET
    contact_description: Optional[str] = strawberry.UNSET
    contact_email: Optional[str] = strawberry.UNSET
    contact_phone: Optional[str] = strawberry.UNSET


@gql.input
class CreatePostInput:
    space_id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    text: str
    image: Optional[Upload] = strawberry.UNSET
    visibility: VisibilityType


@gql.input
class UpdatePostInput:
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
    geolocation: Optional[GeolocationInput] = strawberry.UNSET
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
    geolocation: Optional[GeolocationInput] = strawberry.UNSET
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


@gql.type
class Result:
    success: bool


@gql.type
class Mutation:
    @gql.mutation
    def update_authenticated_user(self, info, input: UpdateAuthenticatedUserInput) -> User:
        current_user = verify_authorized_user(info)
        update_avatar = False

        if input.avatar:
            if input.avatar in ("", {}):
                raise GraphQLError(
                    f"Attribute 'avatar' should be missing or contain a file, but was: '{input.avatar}'"
                )
            else:
                update_avatar = True

        input_dict = to_input_dict(input)
        if input.first_name:
            input_dict["name"] = input.first_name

        serializer = UpdateAuthenticatedUserSerializer(data=input_dict)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            current_user.update(
                name=data.get("name"),
                last_name=data.get("last_name"),
                about_me=data.get("about_me"),
                pronouns=data.get("pronouns"),
                location=data.get("location"),
                geolocation=(GeolocationInput.to_point(data.get("geolocation"))),
                engagement_level=data.get("engagement_level"),
                interests=data.get("interests"),
                sdgs=data.get("sdgs"),
                skills=data.get("skills"),
                avatar=data.get("avatar"),
                update_avatar=update_avatar,
                save=True,
            )
        except Error:
            if update_avatar:
                delete_avatar(data["avatar"])
            raise

        if input.first_name or input.last_name:
            update_ory_user(current_user.id)
            publish_user_name_updated_event(user=current_user)

        return current_user

    @gql.mutation
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
    def delete_post_comment(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        current_user.delete_comment_with_id(post_comment_id=id)

        return Result(success=True)

    @gql.mutation(description="When no userId is provided, the logged in user is used instead.")
    def update_space_user_connection(
        self,
        info,
        space_id: uuid.UUID,
        connection_type: SpaceUserConnectionType,
        connect_action: UpdateConnectionAction,
        user_id: Optional[uuid.UUID] = None,
    ) -> Space:
        current_user = verify_authorized_user(info)
        space = CommunityModel.objects.get(id=space_id)

        cT = SpaceUserConnectionType
        a = UpdateConnectionAction

        if not user_id or current_user.username == user_id:
            # perform for current user
            match (connection_type, connect_action):
                case (cT.MEMBERSHIP_REQUESTOR, a.CONNECT):
                    return current_user.request_membership_to_community_with_name(space.name)
                case (cT.MEMBERSHIP_REQUESTOR, a.DISCONNECT):
                    return current_user.revoke_membership_request_to_community_with_name(space.name)
                case (cT.FOLLOWER, a.CONNECT):
                    return current_user.enable_new_post_notifications_for_community_with_name(space.name)
                case (cT.FOLLOWER, a.DISCONNECT):
                    return current_user.disable_new_post_notifications_for_community_with_name(space.name)
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
                case (cT.ADMINISTRATOR, a.GRANT_ADMIN_ACCESS):
                    return current_user.add_administrator_with_username_to_community_with_name(user_id, space.name)
                case (cT.ADMINISTRATOR, a.REVOKE_ADMIN_ACCESS):
                    return current_user.remove_administrator_with_username_from_community_with_name(
                        user_id, space.name
                    )
                case _:
                    raise GraphQLError(
                        "Operation not allowed",
                        extensions={"code": GraphQLErrorCodes.FORBIDDEN},
                    )

    @gql.mutation
    def create_space_post(self, info: Info, input: CreatePostInput) -> Space:
        current_user = verify_authorized_user(info)

        serializer = CreateCommunityPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        current_user.create_community_encircled_post(**data)

        return CommunityModel.objects.get(id=data.get("space_id"))

    @gql.mutation
    def update_space_post(self, info: Info, id: uuid.UUID, input: UpdatePostInput) -> Space:
        current_user = verify_authorized_user(info)

        serializer = EditCommunityPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        post = current_user.update_community_encircled_post(post_id=id, **data)

        return post.community

    @gql.mutation
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
                current_user.delete()
                logger.info(f"Successfully deleted user {current_user.username}")
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
    def block_user(self, info, user_id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)
        username_of_user_to_block = str(user_id)

        current_user.block_user_with_username(username_of_user_to_block)

        return Result(success=True)

    @gql.mutation
    def validate_space(self, info, input: ValidateSpaceInput) -> Result:
        verify_authorized_user(info)

        serializer = ValidateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)

        return Result(success=True)

    @gql.mutation
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
    def update_space(self, info, input: UpdateSpaceInput) -> Space:
        current_user = verify_authorized_user(info)

        serializer = UpdateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        space = current_user.update_community_with_id(
            community_id=data.get("id"),
            title=data.get("title"),
            description=data.get("description"),
            cover=data.get("cover"),
            topic_ids=data.get("topics"),
            avatar=data.get("avatar"),
            sdg_ids=data.get("sdgs"),
            location=data.get("location"),
            geolocation=(GeolocationInput.to_point(data.get("geolocation"))),
            contact_description=data.get("contact_description"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
        )

        invalidate_discover_spaces_query_cache()

        return space

    @gql.mutation
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
            geolocation=(GeolocationInput.to_point(data.get("geolocation"))),
            regularity=data.get("regularity"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            skills=data.get("skills"),
            thumbnail=data.get("thumbnail"),
        )

    @gql.mutation
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
            geolocation=(GeolocationInput.to_point(data.get("geolocation"))),
            regularity=data.get("regularity"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            skills=data.get("skills"),
            thumbnail=data.get("thumbnail"),
            update_thumbnail=input.thumbnail is not strawberry.UNSET,
        )

    @gql.mutation
    def delete_task(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            current_user.delete_task_with_id(task_id=id)

        return Result(success=True)

    @gql.mutation
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
    def last_seen_notification(self, info, notification_id: uuid.UUID) -> NewNotificationsResponse:
        current_user = verify_authorized_user(info)
        current_user.store_last_seen_notification(notification_id)
        return NewNotificationsResponse(id=current_user.username, status=False)

    @gql.mutation
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
        )

    @gql.mutation
    def delete_collaboration_tool(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            current_user.delete_collaboration_tool(
                collaboration_tool_id=id,
            )

        return Result(success=True)


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        DjangoOptimizerExtension,
        GraphQLErrorExtension,
    ],
)
