import graphene
from datetime import datetime
from django.db import Error, transaction
from django.db.models import Q, Count, F, Value, Prefetch
from django.db.models.functions import Concat
from django.db.models.lookups import IContains
from graphene_django import DjangoObjectType
from graphql import GraphQLError
from graphene_file_upload.scalars import Upload

from openbook_auth.models import UserConnectionStatus, User as UserModel
from openbook_auth.validators import string_not_empty
from openbook_auth.views.authenticated_user.serializers import (
    UpdateAuthenticatedUserSerializer,
)
from openbook_communities.models import (
    Community as CommunityModel,
    Task as TaskModel,
    CommunityMembership as CommunityMembershipModel,
    ExternalLink as ExternalLinkModel,
)
from openbook_common.models import LinkPreview as LinkPreviewModel
from openbook_connections.serializers import UpdateConnectionWithUserSerializer
from openbook_auth.images import delete_avatar

from openbook_insights.models import Insight as InsightModel
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

from logging import getLogger

logger = getLogger(__name__)


# noinspection PyUnresolvedReferences


class ErrorCodes:
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"


class UpdateConnectionWithUserAction:
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"


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
    def data(data, offset, limit):
        return Paged(data=data[offset : offset + limit], total_results=data.count())

    def __init__(self, data, total_results):
        self.data = data
        self.total_results = total_results


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

    def resolve_number_of_posts(self, info):
        return PostModel.objects.filter(insights=self).count()

    def resolve_involved_users(self, info, offset, limit):
        return Paged.data(
            UserModel.objects.select_related("profile")
            .filter(
                Q(curated_insights=self)
                | Q(posts__insights=self)
                | Q(posts_comments__post__insights=self)
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
        return PostCommentModel.objects.filter(post=self).count()

    def resolve_involved_users(self, info, offset, limit):
        return Paged.data(
            UserModel.objects.select_related("profile")
            .filter(Q(posts=self) | Q(posts_comments__post=self))
            .distinct(),
            offset,
            limit,
        )

    def resolve_commenters(self, info, offset, limit):
        return Paged.data(
            UserModel.objects.select_related("profile")
            .filter(posts_comments__post=self)
            .distinct(),
            offset,
            limit,
        )


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


class Space(DjangoObjectType):
    class Meta:
        model = CommunityModel

    members = graphene.List(
        SpaceMember,
        offset=graphene.Int(required=False, default_value=0),
        limit=graphene.Int(required=False, default_value=10),
        required=True,
    )
    main_image = graphene.String()

    def resolve_members(self, info, offset, limit):
        return CommunityMembershipModel.objects.filter(community=self).all()[
            offset : offset + limit
        ]

    def resolve_main_image(self, info):
        return self.cover.name


def spaces_for_filter(topic_id, location, skill_ids, offset, limit):
    topic_filter = Q(topics__id__contains=topic_id) if topic_id is not None else Q()
    location_filter = Q(location__icontains=location) if location is not None else Q()
    skills_filter = Q(tasks__skills__id__in=skill_ids) if skill_ids else Q()

    return Paged.data(
        CommunityModel.objects.prefetch_related("links", "memberships", "tasks")
        .filter(topic_filter, location_filter, skills_filter)
        .annotate(member_count=Count("memberships"))
        .order_by("-member_count", "-created"),
        offset,
        limit,
    )


def resolve_post(id):
    try:
        return get_posts_with_comments_query().get(id=id)
    except PostModel.DoesNotExist:
        raise GraphQLError("Post not found", extensions={"code": ErrorCodes.NOT_FOUND})


def get_posts_with_comments_query():
    return get_posts_only_query().prefetch_related(
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


def get_posts_only_query():
    return (
        PostModel.objects.select_related("creator", "image")
        .prefetch_related("links")
        .prefetch_related(
            Prefetch(
                "mentions",
                queryset=UserModel.objects.select_related("profile"),
            )
        )
    )


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
    )
    discover_spaces = graphene.List(
        DiscoverSpaces,
        topic_ids=graphene.List(
            of_type=graphene.UUID, required=False, default_value=None
        ),
        location=graphene.String(required=False, default_value=None),
        skill_ids=graphene.List(
            of_type=graphene.UUID, required=False, default_value=None
        ),
        offset=graphene.Int(default_value=0),
        limit=graphene.Int(default_value=10),
    )
    space_by_id = graphene.Field(Space, id=graphene.String())
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
            return UserModel.objects.select_related("profile").get(username=id)
        except UserModel.DoesNotExist:
            raise GraphQLError(
                "User not found", extensions={"code": ErrorCodes.NOT_FOUND}
            )

    def resolve_user_by_name(self, info, substring, offset, limit):
        string_not_empty(substring)

        users_to_exclude_ids = (
            [info.context.user.id]
            if info.context and info.context.user and not info.context.user.is_anonymous
            else []
        )
        excludes_filter = ~Q(id__in=users_to_exclude_ids) & Q(profile__isnull=False)
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
                .exclude(profile__isnull=True)
                .exclude(id=info.context.user.id)
                .order_by("-date_joined"),
                offset,
                limit,
            )
        return Paged.data(
            UserModel.objects.select_related("profile")
            .exclude(profile__isnull=True)
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
                .prefetch_related(Prefetch("posts", queryset=get_posts_only_query()))
                .get(id=id)
            )
        except InsightModel.DoesNotExist:
            raise GraphQLError(
                "Insight not found", extensions={"code": ErrorCodes.NOT_FOUND}
            )

    def resolve_post_by_id(self, info, id):
        return resolve_post(id)

    def resolve_topics(self, info, offset, limit):
        return Paged.data(TopicModel.objects.all().order_by("title"), offset, limit)

    def resolve_sdgs(self, info, offset, limit):
        return Paged.data(SDGModel.objects.all().order_by("title"), offset, limit)

    def resolve_skills(self, info, offset, limit):
        return Paged.data(SkillModel.objects.all().order_by("title"), offset, limit)

    def resolve_spaces(self, info, topic_id, location, skill_ids, offset, limit):
        return spaces_for_filter(topic_id, location, skill_ids, offset, limit)

    def resolve_discover_spaces(
        self, info, topic_ids, location, skill_ids, offset, limit
    ):
        result = []

        # get all spaces by location (independent of other filters)
        if location is not None:
            result.append(
                DiscoverSpaces(
                    location=location,
                    spaces=spaces_for_filter(None, location, None, offset, limit),
                )
            )

        # get all spaces by topic (independent of other filters)
        if topic_ids is not None:
            for topic_id in topic_ids or []:
                result.append(
                    DiscoverSpaces(
                        topic_id=topic_id,
                        spaces=spaces_for_filter(topic_id, None, None, offset, limit),
                    )
                )

        # get all spaces by skill_id (including location filter)
        if skill_ids is not None:
            for skill_id in skill_ids:
                result.append(
                    DiscoverSpaces(
                        skill_id=skill_id,
                        location=location,
                        spaces=spaces_for_filter(
                            None, location, [skill_id], offset, limit
                        ),
                    )
                )

        return result

    def resolve_space_by_id(self, info, id):
        try:
            return CommunityModel.objects.get(id=id)
        except CommunityModel.DoesNotExist:
            raise GraphQLError(
                "Space not found", extensions={"code": ErrorCodes.NOT_FOUND}
            )

    def resolve_tasks_by_space_id(
        self, info, space_id, offset=graphene.Int(), limit=graphene.Int()
    ):
        return Paged.data(
            TaskModel.objects.filter(community__id=space_id).order_by("-created"),
            offset,
            limit,
        )

    def resolve_task_by_id(self, info, id):
        try:
            return TaskModel.objects.get(id=id)
        except TaskModel.DoesNotExist:
            raise GraphQLError(
                "Task not found", extensions={"code": ErrorCodes.NOT_FOUND}
            )

    def resolve_notifications(self, info, offset, limit):
        user = info.context.user
        if user.is_anonymous:
            return None
        return Paged.data(
            NotificationModel.objects.filter(owner=user).order_by("-created"),
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


class UpdateConnectionWithUserInput(graphene.InputObjectType):
    user_id = graphene.String()
    action = graphene.String()


class UpdateConnectionWithUserMutation(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(UpdateConnectionWithUserInput)

    Output = User

    @classmethod
    def mutate(cls, root, info, input):
        serializer = UpdateConnectionWithUserSerializer(data=input)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if info.context.user.is_anonymous:
            raise GraphQLError(
                "Unauthorized", extensions={"code": ErrorCodes.UNAUTHORIZED}
            )

        authenticated_user = info.context.user

        user_to_connect_to = authenticated_user.get_user_with_username(
            username=data.get("user_id")
        )

        current_connection_status = (
            authenticated_user.get_connection_status_with_user_id(
                user_id=user_to_connect_to.id
            )
        )

        # Connect action
        if data.get("action") == UpdateConnectionWithUserAction.CONNECT:
            # if current user needs to confirm connection, run confirm_connection_with_user_with_id
            if current_connection_status == UserConnectionStatus.PENDING_CONFIRMATION:
                authenticated_user.confirm_connection_with_user_with_id(
                    user_id=user_to_connect_to.id
                )

            # if there is no connection yet (no requests or pending confirmation), run connect_with_user_with_id
            if current_connection_status == UserConnectionStatus.NOT_CONNECTED:
                authenticated_user.connect_with_user_with_id(
                    user_id=user_to_connect_to.id
                )

        # Disconnect action (only run if current connection status is different than NOT_CONNECTED)
        elif (
            data.get("action") == UpdateConnectionWithUserAction.DISCONNECT
            and current_connection_status != UserConnectionStatus.NOT_CONNECTED
        ):
            authenticated_user.disconnect_from_user_with_id(
                user_id=user_to_connect_to.id
            )

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
        if info.context.user.is_anonymous:
            raise GraphQLError(
                "Unauthorized", extensions={"code": ErrorCodes.UNAUTHORIZED}
            )

        serializer = CommentPostSerializer(data=input)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comment_text = data.get("text")
        post_id = data.get("post_id")

        authenticated_user = info.context.user

        with transaction.atomic():
            post_comment = authenticated_user.comment_post_with_id(
                post_id=post_id, text=comment_text
            )

        return UpdatePostCommentMutation(
            post_comment=post_comment, post_by_id=resolve_post(post_id)
        )


class Mutation(graphene.ObjectType):
    update_authenticated_user = UpdateAuthenticatedUserMutation.Field()
    update_connection_with_user = UpdateConnectionWithUserMutation.Field()
    update_post_comment = UpdatePostCommentMutation.Field()


# noinspection PyTypeChecker
schema = graphene.Schema(query=Query, mutation=Mutation)
