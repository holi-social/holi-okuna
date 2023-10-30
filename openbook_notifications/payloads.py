from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from enum import Enum
from datetime import datetime
from django.conf import settings

if TYPE_CHECKING:
    from openbook_auth.models import User
    from openbook_communities.models import Community


class NotificationType(Enum):
    SPACE_MEMBERSHIP_REQUEST = "SPACE_MEMBERSHIP_REQUEST"


class UserData:
    def __init__(
        self,
        id: str,
        full_name: str,
        email: str,
        avatar_blurhash: Optional[str] = "",
        avatar_default_color: Optional[str] = "",
        avatar: Optional[str] = "",
    ):
        self.id = id
        self.full_name = full_name
        self.email = email
        self.avatar = avatar
        self.avatar_blurhash = avatar_blurhash
        self.avatar_default_color = avatar_default_color

    def to_dict(self):
        return {
            "id": self.id,
            "fullName": self.full_name,
            "email": self.email,
            "avatar": self.avatar,
            "avatarBlurhash": self.avatar_blurhash,
            "avatarDefaultColor": self.avatar_default_color,
        }

    @classmethod
    def from_user(cls, user: User):
        return cls(
            id=str(user.username),
            full_name=user.profile.full_name(),
            email=user.email,
            avatar=user.profile.avatar.url if user.profile.avatar else "",
            avatar_blurhash=user.profile.avatar_blurhash if user.profile.avatar_blurhash else "",
            avatar_default_color=str(user.avatar_default_color) if user.avatar_default_color else "",
        )


class SpaceData:
    def __init__(
        self,
        id: str,
        title: str,
        name: str,
        cover: str,
        avatar_blurhash: str = "",
        avatar_default_color: str = "",
        avatar: Optional[str] = "",
    ):
        self.id = id
        self.name = name
        self.title = title
        self.cover = cover
        self.avatar = avatar
        self.avatar_blurhash = avatar_blurhash
        self.avatar_default_color = avatar_default_color

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "cover": self.cover,
            "avatar": self.avatar,
            "avatarBlurhash": self.avatar_blurhash,
            "avatarDefaultColor": self.avatar_default_color,
        }

    @classmethod
    def from_community(cls, community: Community):
        return cls(
            id=str(community.id),
            name=community.name,
            title=community.title,
            cover=community.cover.url if community.cover else "",
            avatar=community.avatar.url if community.avatar else "",
            avatar_blurhash=community.avatar_blurhash if community.avatar_blurhash else "",
            avatar_default_color=str(community.avatar_default_color) if community.avatar_default_color else "",
        )


class Payload:
    def __init__(self, data: dict, notification_type: str, notification_version: str):
        self.data = data
        self.notification_type = notification_type
        self.notification_version = notification_version

    def to_dict(self) -> dict:
        return {
            "data": self.data,
            "notificationType": self.notification_type,
            "notificationVersion": self.notification_version,
        }


class SpaceMembershipRequestPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"
    request_datetime = datetime.now().isoformat()

    def __init__(self, user: User, space: Community, message: Optional[str] = ""):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "space": SpaceData.from_community(space).to_dict(),
                "requestMessage": message if message else "",
                "requestDatetime": self.request_datetime,
                "collaboratorsLink": f"{settings.APP_URL}/spaces/{space.name}/collaborators/manage?tab=pending&userId={user.username}",
            },
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST.value,
            notification_version=SpaceMembershipRequestPayload.NOTIFICATION_VERSION,
        )
