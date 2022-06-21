import graphene
from graphene_django import DjangoObjectType

from openbook_auth.models import User


class GqlUser(DjangoObjectType):
    class Meta:
        model = User
        fields = ['id']

    first_name = graphene.String()
    middle_name = graphene.String()
    last_name = graphene.String()
    aboutMe = graphene.String()
    pronouns = graphene.String()
    location = graphene.String()
    engagementLevel = graphene.String()
    interests = graphene.List(graphene.String)
    sdgs = graphene.List(graphene.String)
    skills = graphene.List(graphene.String)

    def resolve_first_name(self, info):
        return self.profile.name

    def resolve_middle_name(self, info):
        return self.profile.middle_name

    def resolve_last_name(self, info):
        return self.profile.last_name

    def resolve_aboutMe(self, info):
        return self.profile.about_me

    def resolve_pronouns(self, info):
        return self.profile.pronouns

    def resolve_location(self, info):
        return self.profile.location

    def resolve_engagementLevel(self, info):
        return self.profile.engagementLevel

    def resolve_interests(self, info):
        return self.profile.interests

    def resolve_sdgs(self, info):
        return self.profile.sdgs

    def resolve_skills(self, info):
        return self.profile.skills


class Query(graphene.ObjectType):
    user = graphene.Field(GqlUser, id=graphene.String())
    allUsers = graphene.List(GqlUser)

    def resolve_user(self, info, id):
        user = info.context.user
        print("resolve_user info=%s id=%s user=%s" % (info, id, user))
        if user.is_anonymous:
            # TODO this is just a quick hack and doesn't look at rights/blocks
            return User.objects.get(username=id).first()
        else:
            return user.get_user_with_username(id)

    def resolve_allUsers(self, info, **kwargs):
        return User.objects.all()


# TODO add to schema
class Mutation(graphene.ObjectType):
    createUser = graphene.Field(GqlUser,
                                image=graphene.String(),
                                firstName=graphene.String(),
                                middleName=graphene.String(),
                                lastName=graphene.String(),
                                aboutMe=graphene.String(),
                                pronouns=graphene.String(),
                                location=graphene.String(),
                                engagementLevel=graphene.String(),
                                interests=graphene.List(graphene.String),
                                sdgs=graphene.List(graphene.String),
                                skills=graphene.List(graphene.String))
    updateUser = graphene.Field(GqlUser,
                                image=graphene.String(),
                                firstName=graphene.String(),
                                middleName=graphene.String(),
                                lastName=graphene.String(),
                                aboutMe=graphene.String(),
                                pronouns=graphene.String(),
                                location=graphene.String(),
                                engagementLevel=graphene.String(),
                                interests=graphene.List(graphene.String),
                                sdgs=graphene.List(graphene.String),
                                skills=graphene.List(graphene.String))

    # TODO implement the mutations!!!


schema = graphene.Schema(query=Query, mutation=Mutation)
