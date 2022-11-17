import graphene
from datetime import datetime
from django.db import Error, transaction
from django.db.models import Q
from graphene_django import DjangoObjectType
from graphql import GraphQLError
from graphene_file_upload.scalars import Upload

from openbook_auth.models import UserConnectionStatus, User as UserModel
from openbook_auth.views.authenticated_user.serializers import (
    UpdateAuthenticatedUserSerializer,
)
from openbook_connections.serializers import UpdateConnectionWithUserSerializer
from openbook_auth.images import store_avatar, delete_avatar

from openbook_insights.models import Insight as InsightModel
from openbook_posts.models import Post as PostModel, PostComment as PostCommentModel
from openbook_posts.views.post_comments.serializers import CommentPostSerializer
from openbook_spaces.models import Space as SpaceModel, SpaceMember as SpaceMemberModel
from openbook_spaces.models import Task as TaskModel
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


class Insight(DjangoObjectType):
    class Meta:
        model = InsightModel


class Task(DjangoObjectType):
    class Meta:
        model = TaskModel


class Post(DjangoObjectType):
    class Meta:
        model = PostModel


class PostComment(DjangoObjectType):
    class Meta:
        model = PostCommentModel


class Topic(DjangoObjectType):
    class Meta:
        model = TopicModel


class SDG(DjangoObjectType):
    class Meta:
        model = SDGModel


class Skill(DjangoObjectType):
    class Meta:
        model = SkillModel


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


class Space(DjangoObjectType):
    class Meta:
        model = SpaceModel

    members = graphene.List(
        User,
        offset=graphene.Int(required=False, default_value=0),
        limit=graphene.Int(required=False, default_value=10),
        required=True,
    )

    def resolve_members(self, info, offset, limit):
        return UserModel.objects.filter(spaces_memberships__space=self).all()[
            offset : offset + limit
        ]


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


class Query(graphene.ObjectType):
    authenticated_user = graphene.Field(User)
    user_by_id = graphene.Field(User, id=graphene.String())
    user_suggestions = graphene.List(User, numberOfItems=graphene.Int())
    last_insights = graphene.List(Insight, numberOfItems=graphene.Int())
    insight_by_id = graphene.Field(Insight, id=graphene.String())
    post_by_id = graphene.Field(Post, id=graphene.String())
    spaces = Paged.of(
        Space,
        topic_id=graphene.UUID(required=False, default_value=None),
        location=graphene.String(required=False, default_value=None),
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

    def resolve_authenticated_user(self, info):
        if info.context.user.is_anonymous:
            return None
        return info.context.user

    def resolve_user_by_id(self, info, id):
        try:
            return UserModel.objects.get(username=id)
        except UserModel.DoesNotExist:
            raise GraphQLError(
                "User not found", extensions={"code": ErrorCodes.NOT_FOUND}
            )

    def resolve_user_suggestions(self, info, numberOfItems=graphene.Int()):
        if info.context.user.id:
            return UserModel.objects.exclude(id=info.context.user.id).order_by(
                "-date_joined"
            )[:numberOfItems]
        return UserModel.objects.order_by("-date_joined")[:numberOfItems]

    def resolve_last_insights(self, info, numberOfItems=graphene.Int()):
        return InsightModel.objects.filter(date_published__lte=datetime.now()).order_by(
            "-date_published"
        )[:numberOfItems]

    def resolve_insight_by_id(self, info, id):
        try:
            return InsightModel.objects.get(id=id)
        except InsightModel.DoesNotExist:
            raise GraphQLError(
                "Insight not found", extensions={"code": ErrorCodes.NOT_FOUND}
            )

    def resolve_post_by_id(self, info, id):
        try:
            return PostModel.objects.get(id=id)
        except PostModel.DoesNotExist:
            raise GraphQLError(
                "Post not found", extensions={"code": ErrorCodes.NOT_FOUND}
            )

    def resolve_topics(self, info, offset, limit):
        return Paged.data(TopicModel.objects.all(), offset, limit)

    def resolve_sdgs(self, info, offset, limit):
        return Paged.data(SDGModel.objects.all(), offset, limit)

    def resolve_skills(self, info, offset, limit):
        return Paged.data(SkillModel.objects.all(), offset, limit)

    def resolve_spaces(self, info, topic_id, location, offset, limit):
        topic_filter = Q(topics__id__contains=topic_id) if topic_id is not None else Q()
        location_filter = Q(location=location) if location is not None else Q()

        return Paged.data(
            SpaceModel.objects.filter(topic_filter, location_filter).order_by(
                "-created"
            ),
            offset,
            limit,
        )

    def resolve_space_by_id(self, info, id):
        try:
            return SpaceModel.objects.get(id=id)
        except SpaceModel.DoesNotExist:
            raise GraphQLError(
                "Space not found", extensions={"code": ErrorCodes.NOT_FOUND}
            )

    def resolve_tasks_by_space_id(
        self, info, space_id, offset=graphene.Int(), limit=graphene.Int()
    ):
        return Paged.data(
            TaskModel.objects.filter(space__id=space_id).order_by("-created"),
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

        userToUpdateConnection = authenticated_user.get_user_with_username(
            username=data.get("user_id")
        )

        current_connection_status = (
            authenticated_user.get_connection_status_with_user_id(
                user_id=userToUpdateConnection.id
            )
        )

        # Connect action
        if data.get("action") == UpdateConnectionWithUserAction.CONNECT:
            # if current user needs to confirm connection, run confirm_connection_with_user_with_id
            if current_connection_status == UserConnectionStatus.PENDING_CONFIRMATION:
                authenticated_user.confirm_connection_with_user_with_id(
                    user_id=userToUpdateConnection.id
                )

            # if there is no connection yet (no requests or pending confirmation), run connect_with_user_with_id
            if current_connection_status == UserConnectionStatus.NOT_CONNECTED:
                authenticated_user.connect_with_user_with_id(
                    user_id=userToUpdateConnection.id
                )

        # Disconnect action (only run if current connection status is different than NOT_CONNECTED)
        elif (
            data.get("action") == UpdateConnectionWithUserAction.DISCONNECT
            and current_connection_status != UserConnectionStatus.NOT_CONNECTED
        ):
            authenticated_user.disconnect_from_user_with_id(
                user_id=userToUpdateConnection.id
            )

        return userToUpdateConnection


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

        post_by_id = PostModel.objects.get(id=post_id)

        return UpdatePostCommentMutation(
            post_comment=post_comment, post_by_id=post_by_id
        )


class Mutation(graphene.ObjectType):
    update_authenticated_user = UpdateAuthenticatedUserMutation.Field()
    update_connection_with_user = UpdateConnectionWithUserMutation.Field()
    update_post_comment = UpdatePostCommentMutation.Field()


# noinspection PyTypeChecker
schema = graphene.Schema(query=Query, mutation=Mutation)
