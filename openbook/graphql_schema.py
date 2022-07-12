import graphene
from graphene_django import DjangoObjectType

from openbook_auth.models import User as UserModel
from openbook_auth.views.authenticated_user.serializers import UpdateAuthenticatedUserSerializer


# noinspection PyUnresolvedReferences
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


class Query(graphene.ObjectType):
    authenticated_user = graphene.Field(User)

    def resolve_authenticated_user(self, info):
        if info.context.user.is_anonymous:
            return None
        return info.context.user


class UpdateAuthenticatedUserInput(graphene.InputObjectType):
    avatar = graphene.String()
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

        if 'first_name' in input:
            input['name'] = input.pop('first_name')

        serializer = UpdateAuthenticatedUserSerializer(data=input)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

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
            save=True,
        )

        return UpdateAuthenticatedUserMutation(authenticated_user=authenticated_user)


class Mutation(graphene.ObjectType):
    update_authenticated_user = UpdateAuthenticatedUserMutation.Field()


# noinspection PyTypeChecker
schema = graphene.Schema(query=Query, mutation=Mutation)
