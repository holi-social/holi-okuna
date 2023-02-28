from collections import defaultdict
from datetime import datetime

import requests

import structlog
import hashlib

from django.db.models import Count, F, Value, Prefetch
from django.db.models.functions import Concat
from django.db.models.lookups import IContains
from django.utils.translation import gettext_lazy as _

from strawberry.file_uploads import Upload
from strawberry_django_plus.optimizer import DjangoOptimizerExtension
from django.core.cache import cache
from django.db import Error, transaction
from cacheops import cached_as
from graphql import GraphQLError
from django.conf import settings

from openbook.graphql_errors import GraphQLErrorCodes
from openbook_auth.images import delete_avatar
from openbook_auth.validators import string_not_empty
from openbook_auth.views.authenticated_user.serializers import UpdateAuthenticatedUserSerializer
from openbook_communities.views.communities.serializers import (
    ValidateCommunitySerializer,
    CreateCommunitySerializer,
    UpdateCommunitySerializer,
)
from openbook_connections.serializers import UpdateConnectionWithUserSerializer
from openbook_moderation.models import ModeratedObject
from openbook_posts.views.post_comments.serializers import CommentPostSerializer

from .graphql_types import *

logger = structlog.getLogger(__name__)


def get_id_spaces_count_map(query):
    with_num_spaces = list(query)
    id_to_num_spaces = {}
    for s in with_num_spaces:
        id_to_num_spaces[s.id] = s.num_spaces
    return id_to_num_spaces


@cached_as(CommunityModel)
def spaces_for_filter(offset, limit, topic_id=None, location=None, skill_ids=None, topic_slug=None, skill_slugs=None):
    topic_filter = Q(topics__id__contains=topic_id) if topic_id is not None else Q()
    location_filter = Q(location__icontains=location) if location is not None else Q()
    skills_filter = Q(tasks__skills__id__in=skill_ids) if skill_ids else Q()
    topic_slug_filter = Q(topics__slug__contains=topic_slug) if topic_slug is not None else Q()
    skill_slugs_filter = Q(tasks__skills__slug__in=skill_slugs) if skill_slugs else Q()

    return Paged.of(
        CommunityModel.objects.prefetch_related("links", "memberships__user__profile", "tasks")
        .filter(topic_filter, location_filter, skills_filter, topic_slug_filter, skill_slugs_filter)
        .annotate(member_count=Count("memberships"))
        .order_by("-member_count", "-created"),
        offset,
        limit,
    )


def filter_spaces_by_skill_ids(location, skill_ids, limit):
    return CommunityModel.objects.raw(
        """
            select s.*
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
            select s.* 
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


def resolve_post(user, id):
    try:
        return get_posts_with_comments_query(user).get(id=id)
    except PostModel.DoesNotExist:
        raise GraphQLError("Post not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})


def get_posts_with_comments_query(user):
    return get_posts_only_query(user).prefetch_related(
        Prefetch(
            "comments",
            queryset=PostCommentModel.objects.order_by("created")
            .select_related("commenter__profile")
            .prefetch_related("links")
            .prefetch_related(
                Prefetch(
                    "mentions",
                    queryset=UserModel.objects.select_related("profile"),
                )
            ),
        )
    )


def get_posts_only_query(user):
    return (
        PostModel.objects.filter(PostModel.is_visible_query(user))
        .select_related("creator", "image")
        .prefetch_related("links")
        .prefetch_related(
            Prefetch(
                "mentions",
                queryset=UserModel.objects.select_related("profile"),
            )
        )
    )


def verify_authorized_user(info):
    current_user: UserModel = info.context.request.user
    if not current_user or current_user.is_anonymous:
        raise GraphQLError("Unauthorized", extensions={"code": GraphQLErrorCodes.UNAUTHORIZED})
    return current_user


@gql.type
class Query:
    @gql.django.field
    def authenticated_user(self, info) -> Optional[User]:
        if info.context.request.user.is_anonymous:
            return None
        return info.context.request.user

    @gql.django.field
    def user_by_id(self, info, id: uuid.UUID) -> Optional[User]:
        try:
            context_user = info.context.request.user
            return (
                UserModel.objects.select_related("profile")
                .filter(UserModel.is_visible_query(context_user))
                .get(username=id)
            )
        except UserModel.DoesNotExist:
            raise GraphQLError("User not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

    @gql.django.field
    def user_by_name(self, info, substring: str, offset: int = 0, limit: int = 5) -> Paged[User]:
        string_not_empty(substring)

        users_to_exclude_ids = (
            [info.context.request.user.id]
            if info.context and info.context.request.user and not info.context.request.user.is_anonymous
            else []
        )
        excludes_filter = ~Q(id__in=users_to_exclude_ids) & UserModel.is_visible_query(info.context.request.user)
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
        if info.context.request.user.id:
            return Paged.of(
                UserModel.objects.select_related("profile")
                .filter(UserModel.is_visible_query(info.context.request.user))
                .exclude(id=info.context.request.user.id)
                .order_by("-date_joined"),
                offset,
                limit,
            )
        return Paged.of(
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_query(info.context.request.user))
            .order_by("-date_joined"),
            offset,
            limit,
        )

    @gql.django.field
    def last_insights(self, info, offset: int = 0, limit: int = 10) -> Paged[Insight]:
        return Paged.of(
            InsightModel.objects.filter(date_published__lte=datetime.now()).order_by("-date_published"),
            offset,
            limit,
        )

    @gql.django.field
    def insight_by_id(self, info, id: uuid.UUID) -> Optional[Insight]:
        try:
            return (
                InsightModel.objects.select_related("creator__profile")
                .select_related("topic")
                .filter(date_published__lte=datetime.now())
                .prefetch_related(Prefetch("posts", queryset=get_posts_only_query(info.context.request.user)))
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
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[Space]:
        return spaces_for_filter(offset, limit, topic_id, location, skill_ids, topic_slug, skill_slugs)

    @gql.django.field
    def discover_spaces(
        self,
        topic_ids: Optional[List[Optional[uuid.UUID]]] = None,
        location: Optional[str] = None,
        skill_ids: Optional[List[Optional[uuid.UUID]]] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> List[Optional[DiscoverSpaces]]:

        # Inner utility function for generating a unique cache key consisting of
        # prefix and SHA-256 hash of the discover spaces filters
        # e.g discover_spaces:2cbce4f20876d36947b2db0d6b229c8b2b80741434ceca8e7e3f2258114c2511
        def generate_discover_spaces_hash_key(topic_ids, location, skill_ids, offset, limit):
            key_prefix = "discover_spaces"

            key_parts = []

            if location is not None:
                key_parts.append(location)

            if topic_ids is not None:
                key_parts.extend([str(topic_id) for topic_id in topic_ids])

            if skill_ids is not None:
                key_parts.extend([str(skill_id) for skill_id in skill_ids])

            if offset is not None:
                key_parts.append(str(offset))

            if limit is not None:
                key_parts.append(str(limit))

            key = "_".join(key_parts)

            key_hash = hashlib.sha256(key.encode()).hexdigest()
            return f"{key_prefix}:{key_hash}"

        result = []

        hash_key = generate_discover_spaces_hash_key(topic_ids, location, skill_ids, offset, limit)

        # Check whether the resolver result has already been cached and return it,
        # otherwise, query the database, create the result, and cache it.
        if cache.has_key(hash_key):
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
        verify_authorized_user(info)

        created_spaces = MySpaces(section=_("Created"), type=SpaceUserConnectionType.CREATOR)
        created_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships__user__profile", "tasks")
            .filter(creator=info.context.request.user)
            .annotate(member_count=Count("memberships"))
            .order_by("-member_count", "-created")
        )
        member_spaces = MySpaces(section=_("Joined"), type=SpaceUserConnectionType.MEMBER)
        member_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships__user__profile", "tasks")
            .filter(Q(memberships__user=info.context.request.user), ~Q(creator=info.context.request.user))
            .annotate(member_count=Count("memberships"))
            .order_by("-member_count", "-created")
        )
        followed_spaces = MySpaces(section=_("Following"), type=SpaceUserConnectionType.FOLLOWER)
        followed_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships__user__profile", "tasks")
            .filter(
                Q(notifications_subscriptions__subscriber=info.context.request.user),
                Q(notifications_subscriptions__new_post_notifications=True),
                ~Q(creator=info.context.request.user),
                ~Q(memberships__user=info.context.request.user),
            )
            .annotate(member_count=Count("memberships"))
            .order_by("-member_count", "-created")
        )
        return list(filter(lambda x: x.query.count() > 0, [created_spaces, member_spaces, followed_spaces]))

    @gql.django.field
    def space_by_id(self, info, id: uuid.UUID) -> Optional[Space]:
        try:
            return (
                CommunityModel.objects.prefetch_related("links", "memberships__user__profile", "tasks")
                .filter(ModeratedObject.not_moderated_query(info.context.request.user))
                .get(id=id)
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
        user = info.context.request.user
        if user.is_anonymous:
            return None
        return Paged.of(
            NotificationModel.objects.filter(
                owner=user,
                notification_type__in=[
                    NotificationModel.CONNECTION_REQUEST,
                    NotificationModel.CONNECTION_ACCEPTED,
                    NotificationModel.CONNECTION_CONFIRMED,
                    NotificationModel.POST_COMMENT_USER_MENTION,
                    NotificationModel.COMMUNITY_MEMBERSHIP_REQUEST,
                    NotificationModel.COMMUNITY_MEMBERSHIP_APPROVED,
                ],
            ).order_by("-created"),
            offset,
            limit,
        )


def to_input_dict(input):
    """
    converts a strawberry input object to a dict without null values, so it can be validated
    """
    return {k: v for k, v in strawberry.asdict(input).items() if v != strawberry.UNSET}


@gql.input
class UpdateAuthenticatedUserInput:
    avatar: Optional[Upload] = strawberry.UNSET
    first_name: Optional[str] = strawberry.UNSET
    last_name: Optional[str] = strawberry.UNSET
    about_me: Optional[str] = strawberry.UNSET
    pronouns: Optional[str] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
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


@gql.type
class Result:
    success: bool


@gql.type
class Mutation:
    @gql.mutation
    def update_authenticated_user(self, info, input: UpdateAuthenticatedUserInput) -> User:
        authenticated_user = info.context.request.user
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

        serializer = UpdateAuthenticatedUserSerializer(data=(input_dict))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            authenticated_user.update(
                name=data.get("name"),
                last_name=data.get("last_name"),
                about_me=data.get("about_me"),
                pronouns=data.get("pronouns"),
                location=data.get("location"),
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

        return authenticated_user

    @gql.mutation
    def update_connection_with_user(self, info, input: UpdateConnectionWithUserInput) -> User:
        authenticated_user = verify_authorized_user(info)

        serializer = UpdateConnectionWithUserSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_to_connect_to = authenticated_user.get_user_with_username(username=data.get("user_id"))

        current_connection_status = authenticated_user.get_connection_status_with_user_id(
            user_id=user_to_connect_to.id
        )

        # Connect action
        if input.action == UpdateConnectionAction.CONNECT:
            # if current user needs to confirm connection, run confirm_connection_with_user_with_id
            if current_connection_status == UserConnectionStatus.PENDING_CONFIRMATION:
                authenticated_user.confirm_connection_with_user_with_id(user_id=user_to_connect_to.id)

            # if there is no connection yet (no requests or pending confirmation), run connect_with_user_with_id
            if current_connection_status == UserConnectionStatus.NOT_CONNECTED:
                authenticated_user.connect_with_user_with_id(user_id=user_to_connect_to.id)

        # Disconnect action (only run if current connection status is different than NOT_CONNECTED)
        elif (
            input.action == UpdateConnectionAction.DISCONNECT
            and current_connection_status != UserConnectionStatus.NOT_CONNECTED
        ):
            authenticated_user.disconnect_from_user_with_id(user_id=user_to_connect_to.id)

        return user_to_connect_to

    @gql.mutation
    def update_post_comment(self, info, input: CreatePostCommentInput) -> CreatePostCommentOutput:
        verify_authorized_user(info)

        serializer = CommentPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comment_text = data.get("text")
        post_id = data.get("post_id")

        authenticated_user = info.context.request.user

        with transaction.atomic():
            post_comment = authenticated_user.comment_post_with_id(post_id=post_id, text=comment_text)

        return CreatePostCommentOutput(
            post_comment=post_comment, post_by_id=resolve_post(info.context.request.user, post_id)
        )

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
        space = CommunityModel.objects.get(id=space_id)  # @todo Use name as parameter, same as okuna? w

        cT = SpaceUserConnectionType
        a = UpdateConnectionAction
        if not user_id or current_user.username == user_id:
            # perform for current user
            match (connection_type, connect_action):
                case (cT.MEMBERSHIP_REQUESTOR, a.CONNECT):
                    # Auto-Join Spaces directly. Needs to be removed, once requests with approval are needed
                    return current_user.join_community_with_name(space.name)
                    # return current_user.request_membership_to_community_with_name(space.name)
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
                    return current_user.approve_membership_request_to_community_for_username(user_id, space.name)
                case _:
                    raise GraphQLError("Operation not allowed", extensions={"code": GraphQLErrorCodes.FORBIDDEN})

        return space

    @gql.mutation
    def delete_authenticated_user(self, info) -> Result:
        authenticated_user = info.context.request.user
        headers = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}
        logger.info(f"Deleting user {authenticated_user.username}...")

        response = requests.delete(
            f"{settings.ORY_BASE_URL}/admin/identities/{authenticated_user.username}", headers=headers
        )
        # Ory returns 204 in case of success
        if not response.ok:
            error_message = response.error.error if response.error else "Unknown"
            raise Exception(f"Deleting user {authenticated_user.username} in ory failed: {error_message}")

        with transaction.atomic():
            authenticated_user.delete()

        logger.info(f"Successfully deleted user {authenticated_user.username}")

        return Result(success=True)

    @gql.mutation
    def report_content(
        self, info, object_id: uuid.UUID, content_type: ContentType, description: Optional[str] = None
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
                    f"Unknown ContentType {content_type.value}", extensions={"code": GraphQLErrorCodes.FORBIDDEN}
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
        authenticated_user = verify_authorized_user(info)

        serializer = CreateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return authenticated_user.create_community(
            title=data.get("title"),
            type=CommunityModel.COMMUNITY_TYPE_PUBLIC,
            description=data.get("description"),
            cover=data.get("cover"),
            invites_enabled=True,
            topic_ids=data.get("topics"),
        )

    @gql.mutation
    def update_space(self, info, input: UpdateSpaceInput) -> Space:
        authenticated_user = verify_authorized_user(info)

        serializer = UpdateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return authenticated_user.update_community_with_id(
            community_id=data.get("id"),
            title=data.get("title"),
            description=data.get("description"),
            cover=data.get("cover"),
            topic_ids=data.get("topics"),
            avatar=data.get("avatar"),
            sdg_ids=data.get("sdgs"),
            location=data.get("location"),
        )

    @gql.mutation
    def delete_space(self, info, id: uuid.UUID) -> Result:
        authenticated_user = verify_authorized_user(info)

        with transaction.atomic():
            authenticated_user.delete_community_with_id(
                community_id=id,
            )

        return Result(success=True)

    @gql.mutation
    def update_post_reaction(
        self, info, id: uuid.UUID, reaction_type: ReactionType, reaction_action: ReactionAction
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
        self, info, id: uuid.UUID, reaction_type: ReactionType, reaction_action: ReactionAction
    ) -> PostComment:
        current_user = verify_authorized_user(info)
        post_comment = PostCommentModel.objects.get(id=id)
        if reaction_action == ReactionAction.SET:
            post_comment.react(current_user, reaction_type)
        else:
            post_comment.clear_reaction(current_user, reaction_type)
        return post_comment


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        DjangoOptimizerExtension,
    ],
)
