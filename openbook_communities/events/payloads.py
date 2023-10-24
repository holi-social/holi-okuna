from openbook_communities.models import Community
from openbook_auth.models import User


class UserPayload:
    def __init__(self, id: str, name: str, email: str, identity: str):
        self.id = id
        self.name = name
        self.email = email
        self.identity = identity

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "identity": self.identity}

    @classmethod
    def from_user(cls, user: User):
        return cls(id=str(user.username), name=user.profile.full_name(), email=user.email, identity=user.identity)


class SpacePayload:
    def __init__(self, id: str, name: str, slug: str, avatarDefaultColor: str):
        self.id = id
        self.name = name
        self.slug = slug
        self.avatarDefaultColor = avatarDefaultColor

    def to_dict(self):
        return {"id": self.id, "name": self.name, "slug": self.slug, "avatarDefaultColor": self.avatarDefaultColor}

    @classmethod
    def from_community(cls, community: Community):
        return cls(
            id=str(community.id),
            name=community.title,
            slug=community.name,
            avatarDefaultColor=community.avatar_default_color,
        )
