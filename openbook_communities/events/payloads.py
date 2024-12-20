from openbook_communities.models import Community
from openbook_auth.models import User


class UserPayload:
    def __init__(self, id: str, name: str, email: str, identity: str, avatar: str = ""):
        self.id = id
        self.name = name
        self.email = email
        self.identity = identity
        self.avatar = avatar

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "identity": self.identity,
            "avatar": self.avatar,
        }

    @classmethod
    def from_user(cls, user: User):
        avatar_url = user.profile.avatar.url if user.profile.avatar else None
        return cls(
            id=str(user.username),
            name=user.profile.full_name(),
            email=user.email,
            identity=user.identity,
            avatar=avatar_url,
        )


class SpacePayload:
    def __init__(self, id: str, name: str, slug: str, avatar: str, avatar_default_color: str):
        self.id = id
        self.name = name
        self.avatar = avatar
        self.slug = slug
        self.avatarDefaultColor = avatar_default_color

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "avatar": self.avatar,
            "avatarDefaultColor": self.avatarDefaultColor,
        }

    @classmethod
    def from_community(cls, community: Community):
        if community.avatar:
            avatarUrl = community.avatar.url
        else:
            avatarUrl = None

        return cls(
            id=str(community.id),
            name=community.title,
            slug=community.name,
            avatar=avatarUrl,
            avatar_default_color=community.avatar_default_color,
        )
