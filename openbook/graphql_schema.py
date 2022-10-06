import graphene
from datetime import datetime
from django.db import Error
from graphene_django import DjangoObjectType
from graphql import GraphQLError
from graphene_file_upload.scalars import Upload

from openbook_auth.models import User as UserModel
from openbook_auth.views.authenticated_user.serializers import UpdateAuthenticatedUserSerializer
from openbook_auth.images import store_avatar, delete_old_avatars, delete_image

from openbook_insights.models import Insight as InsightModel
from openbook_posts.models import Post as PostModel

# noinspection PyUnresolvedReferences

class ErrorCodes:
    NOT_FOUND = 'NOT_FOUND'


class User(DjangoObjectType):
    # normally, all fields could just go in here to be automatically included. but for user the fields are actually in
    # user.profile instead of user directly, so we have to write custom resolvers.
    class Meta:
        model = UserModel
        fields = ['id']

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
    interests = graphene.List(graphene.String)
    sdgs = graphene.List(graphene.String)
    skills = graphene.List(graphene.String)

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
        return self.profile.interests

    def resolve_sdgs(self, info):
        return self.profile.sdgs

    def resolve_skills(self, info):
        return self.profile.skills


class Insight(DjangoObjectType):
    class Meta:
        model = InsightModel

    def resolve_posts(self, info, **kwargs):
        return PostModel.objects.filter(insight=self)


class Post(DjangoObjectType):
    class Meta:
        model = PostModel


class Query(graphene.ObjectType):
    authenticated_user = graphene.Field(User)
    user_by_id = graphene.Field(User, id=graphene.String())
    user_suggestions = graphene.List(User, numberOfItems=graphene.Int())
    last_insights = graphene.List(Insight, numberOfItems=graphene.Int())

    def resolve_authenticated_user(self, info):
        if info.context.user.is_anonymous:
            return None
        return info.context.user

    def resolve_user_by_id(self, info, id):
        try:
            return UserModel.objects.get(username=id)
        except UserModel.DoesNotExist:
            raise GraphQLError('User not found', extensions={
                "code": ErrorCodes.NOT_FOUND
            })


    def resolve_user_suggestions(self, info, numberOfItems=graphene.Int()):
        if info.context.user.id:
            return UserModel.objects.exclude(id=info.context.user.id).order_by('-date_joined')[:numberOfItems]
        return UserModel.objects.order_by('-date_joined')[:numberOfItems]

    def resolve_last_insights(self, info, numberOfItems=graphene.Int()):
        return InsightModel.objects.filter(date_published__lte=datetime.now()).order_by('-date_published')[:numberOfItems]


class UpdateAuthenticatedUserInput(graphene.InputObjectType):
    avatar = Upload(required=False)
    first_name = graphene.String()
    last_name = graphene.String()
    about_me = graphene.String()
    pronouns = graphene.String()
    location = graphene.String()
    engagement_level = graphene.String()
    interests = graphene.List(graphene.String)
    sdgs = graphene.List(graphene.String)
    skills = graphene.List(graphene.String)


class UpdateAuthenticatedUserMutation(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(UpdateAuthenticatedUserInput)

    authenticated_user = graphene.Field(User)

    @classmethod
    def mutate(cls, root, info, input):
        authenticated_user = info.context.user
        update_avatar = False

        if 'avatar' in input:
            if input['avatar'] in ("", {}, None):
                raise GraphQLError("Attribute 'avatar' should be missing or contain a file, but was: '{}'".format(input['avatar']))
            else:
                update_avatar = True
                # keep the file to store it after a successful request validation
                avatar_file = input['avatar']
                input['avatar'] = 'avatar_url'

        if 'first_name' in input:
            input['name'] = input.pop('first_name')

        serializer = UpdateAuthenticatedUserSerializer(data=input)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # store the file in the image service. When the update of the user later fails, the old image will still
        # be used. All previous files will be removed, when another avatar is successfully uploaded for the user
        if update_avatar:
            file_id, data['avatar'] = store_avatar(authenticated_user, avatar_file)

        try:
            authenticated_user.update(
                name=data.get('name'),
                last_name=data.get('last_name'),
                about_me=data.get('about_me'),
                pronouns=data.get('pronouns'),
                location=data.get('location'),
                engagement_level=data.get('engagement_level'),
                interests=data.get('interests'),
                sdgs=data.get('sdgs'),
                skills=data.get('skills'),
                avatar=data.get('avatar'),
                update_avatar=update_avatar,
                save=True,
            )
        except Error:
            if update_avatar:
                delete_image(file_id)
            raise

        if update_avatar:
            delete_old_avatars(authenticated_user, file_id)

        return UpdateAuthenticatedUserMutation(authenticated_user=authenticated_user)


class Mutation(graphene.ObjectType):
    update_authenticated_user = UpdateAuthenticatedUserMutation.Field()


# noinspection PyTypeChecker
schema = graphene.Schema(query=Query, mutation=Mutation)
