from typing import Optional

from openbook_auth.models import User
from openbook_communities.models import Community

from django.contrib.gis.geos.point import Point


class UserPayload:
    def __init__(
        self,
        id: str,
        name: str,
        email: str,
        identity: str,
        avatar: Optional[str] = None,
        about_me: Optional[str] = None,
        location: Optional[str] = None,
    ):
        self.id = id
        self.name = name
        self.email = email
        self.identity = identity
        self.avatar = avatar
        self.about_me = about_me
        self.location = location

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "identity": self.identity,
            "avatar": self.avatar,
            "aboutMe": self.about_me,
            "location": self.location,
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
            about_me=user.profile.about_me,
            location=user.profile.location,
        )


class SpacePayload:
    def __init__(
        self,
        id: str,
        name: str,
        slug: str,
        avatar: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        location_lat_lng: Optional[Point] = None,
    ):
        self.id = id
        self.name = name
        self.avatar = avatar
        self.slug = slug
        self.description = description
        self.location = location
        self.location_lat_lng = location_lat_lng

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "avatar": self.avatar,
            "description": self.description,
            "location": self.location,
            "locationLatLng": (
                {
                    "latitude": self.location_lat_lng.x,
                    "longitude": self.location_lat_lng.y,
                }
                if self.location_lat_lng
                else None
            ),
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
            description=community.description,
            location=community.location,
            location_lat_lng=community.geolocation,
        )
