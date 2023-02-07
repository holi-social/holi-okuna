import uuid
from collections import defaultdict
from datetime import datetime
import structlog
import graphene

from cacheops import cached_as
import requests
from django.db import Error, transaction
from django.db.models import Q, Count, F, Value, Prefetch
from django.db.models.functions import Concat
from django.db.models.lookups import IContains
from django.utils.translation import gettext_lazy as _
from graphene_django import DjangoObjectType
from graphene_file_upload.scalars import Upload
from graphql import GraphQLError
from django.conf import settings

from openbook_auth.images import delete_avatar
from openbook_auth.models import UserConnectionStatus, User as UserModel, UserBlock
from openbook_auth.validators import string_not_empty
from openbook_auth.views.authenticated_user.serializers import (
    UpdateAuthenticatedUserSerializer,
)
from openbook_common.models import LinkPreview as LinkPreviewModel
from openbook_communities.models import (
    Community as CommunityModel,
    Task as TaskModel,
    CommunityMembership as CommunityMembershipModel,
    ExternalLink as ExternalLinkModel,
)
from openbook_communities.views.communities.serializers import (
    CreateCommunitySerializer,
    UpdateCommunitySerializer,
    ValidateCommunitySerializer,
)
from openbook_connections.serializers import UpdateConnectionWithUserSerializer
from openbook_insights.models import Insight as InsightModel
from openbook_moderation.models import ModeratedObject
from openbook_notifications.models import Notification as NotificationModel
from openbook_posts.models import (
    Post as PostModel,
    PostComment as PostCommentModel,
    PostImage as PostImageModel,
)
from openbook_posts.views.post_comments.serializers import CommentPostSerializer
from openbook_terms.models import (
    Topic as TopicModel,
    SDG as SDGModel,
    Skill as SkillModel,
)

logger = structlog.getLogger(__name__)


# noinspection PyUnresolvedReferences


class ErrorCodes:
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


class UpdateConnectionAction(graphene.Enum):
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"


class ContentType(graphene.Enum):
    POST = "POST"
    POST_COMMENT = "POST_COMMENT"
    USER = "USER"
    SPACE = "SPACE"


class Paged(graphene.ObjectType):
    @staticmethod
    def of(paged_class, **kwargs):
        if "offset" not in kwargs:
            kwargs["offset"] = graphene.Int(default_value=0)
        if "limit" not in kwargs:
            kwargs["limit"] = graphene.Int(default_value=10)
        if "required" not in kwargs:
            kwargs["required"] = True

        PagedType = type(
            f"Paged{paged_class.__name__}List",
            (Paged,),
            {
                "data": graphene.List(paged_class, required=True),
                "total_results": graphene.Int(required=True),
            },
        )
        return graphene.Field(
            PagedType,
            **kwargs,
        )

    @staticmethod
    def data(query, offset, limit):
        return Paged(data=query[offset : offset + limit], total_results=query.count())

    def __init__(self, data=[], total_results=None):
        self.data = data
        self.total_results = total_results if total_results is not None else len(data)


class Task(DjangoObjectType):
    class Meta:
        model = TaskModel


class ExternalLink(DjangoObjectType):
    class Meta:
        model = ExternalLinkModel


class Topic(DjangoObjectType):
    class Meta:
        model = TopicModel


class SDG(DjangoObjectType):
    class Meta:
        model = SDGModel


class Skill(DjangoObjectType):
    class Meta:
        model = SkillModel


class PostImage(DjangoObjectType):
    class Meta:
        model = PostImageModel
        exclude = ["image"]  # instead, expose it as "url"

    url = graphene.NonNull(graphene.String)

    def resolve_url(self, info):
        return self.image


class LinkPreview(DjangoObjectType):
    class Meta:
        model = LinkPreviewModel

    origin = graphene.String(required=True)

    def resolve_origin(self, info):
        return self.get_origin()


class User(DjangoObjectType):
    # normally, all fields could just go in here to be automatically included. but for user the fields are actually in
    # user.profile instead of user directly, so we have to write custom resolvers.
    class Meta:
        model = UserModel
        fields = ["id"]

    id = graphene.String()
    avatar = graphene.String()
    first_name = graphene.String()
    last_name = graphene.String()
    full_name = graphene.String(required=True, description="Can be an empty string")
    about_me = graphene.String()
    pronouns = graphene.String()
    location = graphene.String()
    avatar_default_color = graphene.NonNull(graphene.String)
    avatar_label = graphene.NonNull(graphene.String)
    engagement_level = graphene.String()
    interests = graphene.List(Topic)
    sdgs = graphene.List(SDG)
    skills = graphene.List(Skill)
    connection_status_to_myself = graphene.String()

    def resolve_id(self, info):
        return self.username

    def resolve_avatar(self, info):
        return self.profile.avatar

    def resolve_first_name(self, info):
        return self.profile.name

    def resolve_last_name(self, info):
        return self.profile.last_name

    def resolve_full_name(self, info):
        return self.profile.full_name()

    def resolve_about_me(self, info):
        return self.profile.about_me

    def resolve_pronouns(self, info):
        return self.profile.pronouns

    def resolve_location(self, info):
        return self.profile.location

    def resolve_avatar_default_color(self, info):
        return self.avatar_default_color

    def resolve_avatar_label(self, info):
        return self.avatar_label

    def resolve_engagement_level(self, info):
        return self.profile.engagement_level

    def resolve_interests(self, info):
        return self.profile.interests.all()

    def resolve_sdgs(self, info):
        return self.profile.sdgs.all()

    def resolve_skills(self, info):
        return self.profile.skills.all()

    def resolve_connection_status_to_myself(self, info):
        if info.context.user.is_anonymous:
            return None
        return info.context.user.get_connection_status_with_user_id(user_id=self.id)


class Insight(DjangoObjectType):
    class Meta:
        model = InsightModel

    number_of_posts = graphene.Int(required=True)
    involved_users = Paged.of(
        User,
        description="A list of all users involved. Curator of the insight, Authors of all the posts and all commenters of those posts",
    )

    def resolve_posts(self, info):
        return (
            PostModel.objects.filter(PostModel.is_visible_query(info.context.user))
            .filter(insights=self)
            .order_by("created")
            .all()
        )

    def resolve_number_of_posts(self, info):
        return PostModel.objects.filter(PostModel.is_visible_query(info.context.user)).filter(insights=self).count()

    def resolve_involved_users(self, info, offset, limit):
        return Paged.data(
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_query(info.context.user))
            .filter(
                Q(curated_insights=self)
                | (Q(posts__insights=self) & PostModel.is_visible_query(info.context.user, "posts__"))
                | (
                    Q(posts_comments__post__insights=self)
                    & PostModel.is_visible_query(info.context.user, "posts_comments__post__")
                )
            )
            .distinct(),
            offset,
            limit,
        )


class Post(DjangoObjectType):
    class Meta:
        model = PostModel

    image = graphene.Field(PostImage)
    links = graphene.List(LinkPreview)
    number_of_comments = graphene.Int(required=True)
    involved_users = Paged.of(
        User,
        description="A list of all users involved. Author of the post plus all commenters",
    )
    commenters = Paged.of(User)

    def resolve_image(self, info):
        if hasattr(self, "image"):
            return self.image
        return None

    def resolve_links(self, info):
        return self.links.all()

    def resolve_number_of_comments(self, info):
        return (  # self.resolve_comments(info).count()
            PostCommentModel.objects.filter(post=self)
            .filter(PostCommentModel.is_visible_query(info.context.user))
            .count()
        )

    def resolve_involved_users(self, info, offset, limit):
        return Paged.data(
            UserModel.objects.select_related("profile")
            .filter(
                (Q(posts=self) & PostModel.is_visible_query(info.context.user, "posts__"))
                | (
                    Q(posts_comments__post=self)
                    & PostCommentModel.is_visible_query(info.context.user, "posts_comments__")
                )
            )
            .filter(UserModel.is_visible_query(info.context.user))
            .distinct(),
            offset,
            limit,
        )

    def resolve_commenters(self, info, offset, limit):
        return Paged.data(
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_query(info.context.user))
            .filter(posts_comments__post=self)
            .distinct(),
            offset,
            limit,
        )

    def resolve_comments(self, info):
        return PostCommentModel.objects.filter(PostCommentModel.is_visible_query(info.context.user)).filter(post=self)


class PostComment(DjangoObjectType):
    class Meta:
        model = PostCommentModel

    creator = graphene.Field(User, required=True, description="Synonym for commenter")
    links = graphene.List(LinkPreview)

    def resolve_creator(self, info):
        return self.commenter

    def resolve_links(self, info):
        return self.links.all()


class SpaceMember(DjangoObjectType):
    class Meta:
        model = CommunityMembershipModel


class SpaceUserConnectionType(graphene.Enum):
    FOLLOWER = "FOLLOWER"
    MEMBERSHIP_REQUESTOR = "MEMBERSHIP_REQUESTOR"
    MEMBER = "MEMBER"
    CREATOR = "CREATOR"
    ADMINISTRATOR = "ADMINISTRATOR"


class Space(DjangoObjectType):
    class Meta:
        model = CommunityModel

    members = Paged.of(
        SpaceMember,
        description="A list of all active members and their role",
    )
    main_image = graphene.String()
    connection_status_to_myself = graphene.List(SpaceUserConnectionType)

    def resolve_members(self, info, offset, limit):
        return Paged.data(
            CommunityMembershipModel.objects.filter(community=self),
            offset,
            limit,
        )

    def resolve_main_image(self, info):
        return self.cover.name

    def resolve_connection_status_to_myself(self, info):
        current_user: UserModel = info.context.user
        if current_user.is_anonymous:
            return []

        roles = []

        if current_user.are_new_post_notifications_enabled_for_community(self):
            roles.append(SpaceUserConnectionType.FOLLOWER)

        if current_user.is_membership_requestor_of_community_with_name(self.name):
            roles.append(SpaceUserConnectionType.MEMBERSHIP_REQUESTOR)

        if self.creator == current_user:
            roles.append(SpaceUserConnectionType.CREATOR)

        if membership := CommunityMembershipModel.objects.filter(community=self, user=current_user).first():
            roles.append(SpaceUserConnectionType.MEMBER)

            if membership.is_administrator:
                roles.append(SpaceUserConnectionType.ADMINISTRATOR)

            # if membership.is_moderator:
            # roles.append(xxx)
            # pass

        return roles


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

    return Paged.data(
        CommunityModel.objects.prefetch_related("links", "memberships", "tasks")
        .filter(topic_filter, location_filter, skills_filter, topic_slug_filter, skill_slugs_filter)
        .annotate(member_count=Count("memberships"))
        .order_by("-member_count", "-created"),
        offset,
        limit,
    )


def resolve_post(user, id):
    try:
        return get_posts_with_comments_query(user).get(id=id)
    except PostModel.DoesNotExist:
        raise GraphQLError("Post not found", extensions={"code": ErrorCodes.NOT_FOUND})


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
    current_user: UserModel = info.context.user
    if not current_user or current_user.is_anonymous:
        raise GraphQLError("Unauthorized", extensions={"code": ErrorCodes.UNAUTHORIZED})
    return current_user


class NotificationOptions(graphene.ObjectType):
    user = graphene.Field(User)
    post = graphene.Field(Post)
    post_comment = graphene.Field(PostComment)
    space = graphene.Field(Space)


class Notification(DjangoObjectType):
    class Meta:
        model = NotificationModel
        exclude = ["object_id"]

    options = graphene.Field(NotificationOptions)

    def resolve_options(self, info):
        options = self.get_options()
        return NotificationOptions(
            user=options.get("user"),
            post=options.get("post"),
            post_comment=options.get("post_comment"),
            space=options.get("space"),
        )


class DiscoverSpaces(graphene.ObjectType):
    topic_id = graphene.UUID()
    location = graphene.String()
    skill_id = graphene.UUID()
    spaces = Paged.of(Space)


class MySpaces(graphene.ObjectType):
    section = graphene.String()
    type = SpaceUserConnectionType()
    spaces = Paged.of(Space)

    def resolve_spaces(self, info, offset, limit):
        """
        When spaces are already resolved, they are returned.
        Otherwise: When a query is provided, it is used to create a paged result.
        """
        if self.spaces is not None:
            return self.spaces
        if hasattr(self, "query"):
            return Paged.data(self.query, offset, limit)
        return Paged()


class Query(graphene.ObjectType):
    authenticated_user = graphene.Field(User)
    user_by_id = graphene.Field(User, id=graphene.String())
    user_by_name = Paged.of(
        User,
        substring=graphene.String(required=True),
        limit=graphene.Int(default_value=5),
    )
    user_suggestions = Paged.of(User)
    last_insights = Paged.of(Insight)
    insight_by_id = graphene.Field(Insight, id=graphene.String())
    post_by_id = graphene.Field(Post, id=graphene.String())
    spaces = Paged.of(
        Space,
        topic_id=graphene.UUID(required=False, default_value=None),
        location=graphene.String(required=False, default_value=None),
        skill_ids=graphene.List(graphene.UUID, default_value=None),
        topic_slug=graphene.String(required=False, default_value=None),
        skill_slugs=graphene.List(graphene.String, default_value=None),
    )
    discover_spaces = graphene.List(
        DiscoverSpaces,
        topic_ids=graphene.List(of_type=graphene.UUID, required=False, default_value=None),
        location=graphene.String(required=False, default_value=None),
        skill_ids=graphene.List(of_type=graphene.UUID, required=False, default_value=None),
        offset=graphene.Int(default_value=0),
        limit=graphene.Int(default_value=10),
    )
    my_spaces = graphene.List(MySpaces)
    space_by_id = graphene.Field(Space, id=graphene.UUID())
    tasks_by_space_id = Paged.of(
        Task,
        space_id=graphene.String(),
    )
    task_by_id = graphene.Field(Task, id=graphene.String())
    topics = Paged.of(Topic, limit=graphene.Int(default_value=50))
    sdgs = Paged.of(SDG, limit=graphene.Int(default_value=50))
    skills = Paged.of(Skill, limit=graphene.Int(default_value=50))
    notifications = Paged.of(Notification)

    def resolve_authenticated_user(self, info):
        if info.context.user.is_anonymous:
            return None
        return info.context.user

    def resolve_user_by_id(self, info, id):
        try:
            context_user = info.context.user
            return (
                UserModel.objects.select_related("profile")
                .filter(UserModel.is_visible_query(context_user))
                .get(username=id)
            )
        except UserModel.DoesNotExist:
            raise GraphQLError("User not found", extensions={"code": ErrorCodes.NOT_FOUND})

    def resolve_user_by_name(self, info, substring, offset, limit):
        string_not_empty(substring)

        users_to_exclude_ids = (
            [info.context.user.id] if info.context and info.context.user and not info.context.user.is_anonymous else []
        )
        excludes_filter = ~Q(id__in=users_to_exclude_ids) & UserModel.is_visible_query(info.context.user)
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

    def resolve_user_suggestions(self, info, offset, limit):
        if info.context.user.id:
            return Paged.data(
                UserModel.objects.select_related("profile")
                .filter(UserModel.is_visible_query(info.context.user))
                .exclude(id=info.context.user.id)
                .order_by("-date_joined"),
                offset,
                limit,
            )
        return Paged.data(
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_query(info.context.user))
            .order_by("-date_joined"),
            offset,
            limit,
        )

    def resolve_last_insights(self, info, offset, limit):
        return Paged.data(
            InsightModel.objects.select_related("creator__profile")
            .select_related("topic")
            .filter(date_published__lte=datetime.now())
            .order_by("-date_published"),
            offset,
            limit,
        )

    def resolve_insight_by_id(self, info, id):
        try:
            return (
                InsightModel.objects.select_related("creator__profile")
                .select_related("topic")
                .filter(date_published__lte=datetime.now())
                .prefetch_related(Prefetch("posts", queryset=get_posts_only_query(info.context.user)))
                .get(id=id)
            )
        except InsightModel.DoesNotExist:
            raise GraphQLError("Insight not found", extensions={"code": ErrorCodes.NOT_FOUND})

    def resolve_post_by_id(self, info, id):
        return resolve_post(info.context.user, id)

    def resolve_topics(self, info, offset, limit):
        return Paged.data(TopicModel.objects.all().order_by("title"), offset, limit)

    def resolve_sdgs(self, info, offset, limit):
        return Paged.data(SDGModel.objects.all().order_by("title"), offset, limit)

    def resolve_skills(self, info, offset, limit):
        return Paged.data(SkillModel.objects.all().order_by("title"), offset, limit)

    def resolve_spaces(self, info, topic_id, location, skill_ids, topic_slug, skill_slugs, offset, limit):
        return spaces_for_filter(offset, limit, topic_id, location, skill_ids, topic_slug, skill_slugs)

    def resolve_discover_spaces(self, info, topic_ids, location, skill_ids, offset, limit):
        result = []

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

            spaces_from_db = CommunityModel.objects.raw(
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
            )
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

            spaces_from_db = CommunityModel.objects.raw(
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
            )
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

        return result

    def resolve_my_spaces(self, info):
        verify_authorized_user(info)

        created_spaces = MySpaces(section=_("Created"), type=SpaceUserConnectionType.CREATOR)
        created_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships", "tasks")
            .filter(creator=info.context.user)
            .annotate(member_count=Count("memberships"))
            .order_by("-member_count", "-created")
        )
        member_spaces = MySpaces(section=_("Joined"), type=SpaceUserConnectionType.MEMBER)
        member_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships", "tasks")
            .filter(Q(memberships__user=info.context.user), ~Q(creator=info.context.user))
            .annotate(member_count=Count("memberships"))
            .order_by("-member_count", "-created")
        )
        followed_spaces = MySpaces(section=_("Following"), type=SpaceUserConnectionType.FOLLOWER)
        followed_spaces.query = (
            CommunityModel.objects.prefetch_related("links", "memberships", "tasks")
            .filter(
                Q(notifications_subscriptions__subscriber=info.context.user),
                Q(notifications_subscriptions__new_post_notifications=True),
                ~Q(creator=info.context.user),
                ~Q(memberships__user=info.context.user),
            )
            .annotate(member_count=Count("memberships"))
            .order_by("-member_count", "-created")
        )
        return filter(lambda x: x.query.count() > 0, [created_spaces, member_spaces, followed_spaces])

    def resolve_space_by_id(self, info, id):
        try:
            return CommunityModel.objects.filter(ModeratedObject.not_moderated_query(info.context.user)).get(id=id)
        except CommunityModel.DoesNotExist:
            raise GraphQLError("Space not found", extensions={"code": ErrorCodes.NOT_FOUND})

    def resolve_tasks_by_space_id(self, info, space_id, offset=graphene.Int(), limit=graphene.Int()):
        return Paged.data(
            TaskModel.objects.filter(community__id=space_id).order_by("-created"),
            offset,
            limit,
        )

    def resolve_task_by_id(self, info, id):
        try:
            return TaskModel.objects.get(id=id)
        except TaskModel.DoesNotExist:
            raise GraphQLError("Task not found", extensions={"code": ErrorCodes.NOT_FOUND})

    def resolve_notifications(self, info, offset, limit):
        user = info.context.user
        if user.is_anonymous:
            return None
        return Paged.data(
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


class UpdateAuthenticatedUserInput(graphene.InputObjectType):
    avatar = Upload(required=False)
    first_name = graphene.String()
    last_name = graphene.String()
    about_me = graphene.String()
    pronouns = graphene.String()
    location = graphene.String()
    engagement_level = graphene.String()
    interests = graphene.List(graphene.UUID)
    sdgs = graphene.List(graphene.UUID)
    skills = graphene.List(graphene.UUID)


class UpdateAuthenticatedUserMutation(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(UpdateAuthenticatedUserInput)

    Output = User

    @classmethod
    def mutate(cls, root, info, input):
        authenticated_user = info.context.user
        update_avatar = False

        if "avatar" in input:
            if input["avatar"] in ("", {}, None):
                raise GraphQLError(
                    f"Attribute 'avatar' should be missing or contain a file, but was: '{input['avatar']}'"
                )
            else:
                update_avatar = True

        if "first_name" in input:
            input["name"] = input.pop("first_name")

        serializer = UpdateAuthenticatedUserSerializer(data=input)
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


class DeleteAuthenticatedUserMutation(graphene.Mutation):
    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info):
        authenticated_user = info.context.user
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

        return DeleteAuthenticatedUserMutation(success=True)


class UpdateConnectionWithUserInput(graphene.InputObjectType):
    user_id = graphene.String()
    action = UpdateConnectionAction(required=True)


class UpdateConnectionWithUserMutation(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(UpdateConnectionWithUserInput)

    Output = User

    @classmethod
    def mutate(cls, root, info, input):
        serializer = UpdateConnectionWithUserSerializer(data=input)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        verify_authorized_user(info)

        authenticated_user = info.context.user

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


class CreatePostCommentInput(graphene.InputObjectType):
    post_id = graphene.String()
    text = graphene.String()


class UpdatePostCommentMutation(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(CreatePostCommentInput)

    post_comment = graphene.Field(PostComment)
    post_by_id = graphene.Field(Post)

    @classmethod
    def mutate(cls, root, info, input):
        verify_authorized_user(info)

        serializer = CommentPostSerializer(data=input)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comment_text = data.get("text")
        post_id = data.get("post_id")

        authenticated_user = info.context.user

        with transaction.atomic():
            post_comment = authenticated_user.comment_post_with_id(post_id=post_id, text=comment_text)

        return UpdatePostCommentMutation(
            post_comment=post_comment, post_by_id=resolve_post(info.context.user, post_id)
        )


class UpdateSpaceUserConnectionMutation(graphene.Mutation):
    class Arguments:
        space_id = graphene.UUID(required=True)
        user_id = graphene.UUID(description="If not provided, the logged in user is used instead.")
        connection_type = SpaceUserConnectionType(required=True)
        connect_action = UpdateConnectionAction(required=True)

    Output = Space

    @classmethod
    def mutate(cls, root, info, space_id, connection_type, connect_action, user_id=None):
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
                    raise GraphQLError("Operation not allowed", extensions={"code": ErrorCodes.FORBIDDEN})
        else:
            # perform for other user
            match (connection_type, connect_action):
                case (cT.MEMBERSHIP_REQUESTOR, a.DISCONNECT):
                    return current_user.revoke_membership_request_to_community_for_username(user_id, space.name)
                case (cT.MEMBER, a.CONNECT):
                    return current_user.approve_membership_request_to_community_for_username(user_id, space.name)
                case _:
                    raise GraphQLError("Operation not allowed", extensions={"code": ErrorCodes.FORBIDDEN})

        return space


class BlockUserMutation(graphene.Mutation):
    class Arguments:
        user_id = graphene.UUID(description="The user to block")

    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, user_id):
        current_user = verify_authorized_user(info)
        username_of_user_to_block = str(user_id)

        current_user.block_user_with_username(username_of_user_to_block)

        return BlockUserMutation(success=True)


class ReportContentMutation(graphene.Mutation):
    class Arguments:
        object_id = graphene.UUID(required=True)
        content_type = ContentType(required=True)
        description = graphene.String()

    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, object_id, content_type, description=None):
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
                    f"Unknown ContentType {content_type.value}", extensions={"code": ErrorCodes.FORBIDDEN}
                )

        return ReportContentMutation(success=True)


class ValidateSpaceInput(graphene.InputObjectType):
    title = graphene.String()
    description = graphene.String()
    topics = graphene.List(graphene.UUID)
    cover = Upload(required=False)


class ValidateSpaceMutation(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(ValidateSpaceInput)

    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, input):
        verify_authorized_user(info)

        serializer = ValidateCommunitySerializer(data=input)
        serializer.is_valid(raise_exception=True)

        return ValidateSpaceMutation(success=True)


class CreateSpaceInput(graphene.InputObjectType):
    title = graphene.String(required=True)
    description = graphene.String(required=True)
    topics = graphene.List(graphene.UUID, required=True)
    cover = Upload(required=True)


class CreateSpaceMutation(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(CreateSpaceInput)

    Output = Space

    @classmethod
    def mutate(cls, root, info, input):
        authenticated_user = verify_authorized_user(info)

        serializer = CreateCommunitySerializer(data=input)
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


class UpdateSpaceInput(graphene.InputObjectType):
    id = graphene.UUID()
    title = graphene.String()
    description = graphene.String()
    topics = graphene.List(graphene.UUID)
    cover = Upload(required=False)


class UpdateSpaceMutation(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(UpdateSpaceInput)

    Output = Space

    @classmethod
    def mutate(cls, root, info, input):
        authenticated_user = verify_authorized_user(info)

        serializer = UpdateCommunitySerializer(data=input)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return authenticated_user.update_community_with_id(
            community_id=data.get("id"),
            title=data.get("title"),
            description=data.get("description"),
            cover=data.get("cover"),
            topic_ids=data.get("topics"),
        )


class Mutation(graphene.ObjectType):
    update_authenticated_user = UpdateAuthenticatedUserMutation.Field()
    update_connection_with_user = UpdateConnectionWithUserMutation.Field()
    update_post_comment = UpdatePostCommentMutation.Field()
    update_space_user_connection = UpdateSpaceUserConnectionMutation.Field()
    delete_authenticated_user = DeleteAuthenticatedUserMutation.Field()
    report_content = ReportContentMutation.Field()
    block_user = BlockUserMutation.Field()
    validate_space = ValidateSpaceMutation.Field()
    create_space = CreateSpaceMutation.Field()
    update_space = UpdateSpaceMutation.Field()


# noinspection PyTypeChecker
schema = graphene.Schema(query=Query, mutation=Mutation)
