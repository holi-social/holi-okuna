import graphene
from graphene_django import DjangoObjectType
from graphene_django.rest_framework.mutation import SerializerMutation

from openbook_auth.models import User
from openbook_auth.views.authenticated_user.serializers import UpdateAuthenticatedUserSerializer


class GqlUser(DjangoObjectType):
    # normally, all fields could just go in here to be automatically included. but for user the fields are actually in
    # user.profile instead of user directly, so we have to write custom resolvers.
    class Meta:
        model = User
        fields = ['id']

    avatar = graphene.String()
    username = graphene.String()
    first_name = graphene.String()
    middle_name = graphene.String()
    last_name = graphene.String()
    aboutMe = graphene.String()
    pronouns = graphene.String()
    location = graphene.String()
    engagement_level = graphene.String()
    interests = graphene.List(graphene.String)
    sdgs = graphene.List(graphene.String)
    skills = graphene.List(graphene.String)

    def resolve_avatar(self, info):
        return self.profile.avatar

    def resolve_first_name(self, info):
        return self.profile.name

    def resolve_middle_name(self, info):
        return self.profile.middle_name

    def resolve_last_name(self, info):
        return self.profile.last_name

    def resolve_about_me(self, info):
        return self.profile.about_me

    def resolve_pronouns(self, info):
        return self.profile.pronouns

    def resolve_location(self, info):
        return self.profile.location

    def resolve_engagement_level(self, info):
        return self.profile.engagement_level

    def resolve_interests(self, info):
        return self.profile.interests

    def resolve_sdgs(self, info):
        return self.profile.sdgs

    def resolve_skills(self, info):
        return self.profile.skills


class Query(graphene.ObjectType):
    user = graphene.Field(GqlUser, id=graphene.String())
    all_users = graphene.List(GqlUser)

    def resolve_user(self, info, id):
        user = info.context.user
        print("resolve_user info=%s id=%s user=%s" % (info, id, user))
        if user.is_anonymous:
            # TODO this is just a quick hack and doesn't look at rights/blocks
            return User.objects.get(username=id).first()
        else:
            return user.get_user_with_username(id)

    def resolve_all_users(self, info, **kwargs):
        return User.objects.all()


# TODO remove, as they're within class Arguments?????
class UserInput(graphene.InputObjectType):
    avatar = graphene.String()
    firstName = graphene.String()
    middleName = graphene.String()
    lastName = graphene.String()
    aboutMe = graphene.String()
    pronouns = graphene.String()
    location = graphene.String()
    engagementLevel = graphene.String()
    interests = graphene.List(graphene.String)
    sdgs = graphene.List(graphene.String)
    skills = graphene.List(graphene.String)


# TODO "original" API definition receives an id: ID! field to indicate which user should be updated. This field is
#  redundant as a user can only edit himself anyways, so the authorization headers can be used to identify the user.
#  -> Remove the id field from the API definition?
class UpdateUserMutation(graphene.Mutation):
    class Arguments:
        user = graphene.Argument(UserInput)

    user = graphene.Field(GqlUser)

    @classmethod
    def mutate(cls, root, info, user):
        authenticated_user = info.context.user
        print("UpdateUserMutation (user=%s,user_input=%s)" % (authenticated_user, user))
        # TODO validation + implementation here is copy/pasted from AuthenticatedUser.patch, this would need to be
        #  refactored into a non-REST-specific business logic method
        serializer = UpdateAuthenticatedUserSerializer(data=user)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        authenticated_user.update(
            name=data.get('name'),
            location=data.get('location'),
            about_me=data.get('about_me'),
            save=True,  # TODO maybe set to false or remove after refactoring
            middle_name=data.get('middle_name'),
            last_name=data.get('last_name'),
            pronouns=data.get('pronouns'),
            engagement_level=data.get('engagement_level'),
            interests=data.get('interests'),
            sdgs=data.get('sdgs'),  # TODO receives a "JSONString" instead of an array :/
            skills=data.get('skills'),
        )
        print("UpdateUserMutation (user=%s)" % authenticated_user)
        return UpdateUserMutation(user=authenticated_user)
        # TODO do a few more things as in openbook_auth.views.authenticated_user.views.AuthenticatedUser.patch or
        #  refactor user.update() method to include the updating of these "few more things" as the business logic should
        #  not reside in the API layer anyway


class Mutation(graphene.ObjectType):
    # TODO remove function createUser from API definition? it should not exist, users are automatically generated once
    #  Okuna receives a valid token, so we only need an update mutation
    updateUser = UpdateUserMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
