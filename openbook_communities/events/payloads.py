from openbook_communities.models import Community
from openbook_auth.models import User


class UserPayload:
    def __init__(self, id: str, name: str, email: str):
        self.id = id
        self.name = name
        self.email = email

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}

    @classmethod
    def from_user(cls, user: User):
        return cls(id=str(user.username), name=user.profile.name, email=user.email)


class SpacePayload:
    def __init__(self, id: str, name: str, slug: str):
        self.id = id
        self.name = name
        self.slug = slug

    def to_dict(self):
        return {"id": self.id, "name": self.name, "slug": self.slug}

    @classmethod
    def from_community(cls, community: Community):
        return cls(id=str(community.id), name=community.title, slug=community.name)
