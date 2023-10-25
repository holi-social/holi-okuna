from enum import Enum
from datetime import datetime
from typing import Optional
from django.conf import settings

from openbook_auth.models import User
from openbook_communities.models import Community


class NotificationType(Enum):
    SPACE_MEMBERSHIP_REQUEST = "SPACE_MEMBERSHIP_REQUEST"


class UserData:
    def __init__(self, id: str, full_name: str, email: str, avatar: Optional[str] = ""):
        self.id = id
        self.full_name = full_name
        self.email = email
        self.avatar = avatar

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "avatar": self.avatar,
        }

    @classmethod
    def from_user(cls, user: User):
        return cls(
            id=str(user.username),
            full_name=user.profile.full_name(),
            email=user.email,
            avatar=user.profile.avatar.url if user.profile.avatar else "",
        )


class SpaceData:
    def __init__(self, id: str, title: str, name: str, cover: str, avatar: Optional[str] = ""):
        self.id = id
        self.name = name
        self.title = title
        self.cover = cover
        self.avatar = avatar

    def to_dict(self):
        return {"id": self.id, "name": self.name, "title": self.title, "cover": self.cover, "avatar": self.avatar}

    @classmethod
    def from_community(cls, community: Community):
        return cls(
            id=str(community.id),
            name=community.name,
            title=community.title,
            cover=community.cover.url if community.cover else "",
            avatar=community.avatar.url if community.avatar else "",
        )


class Payload:
    def __init__(self, data: dict, notification_type: str, notification_version: str):
        self.data = data
        self.notification_type = notification_type
        self.notification_version = notification_version

    def to_dict(self) -> dict:
        return {
            "data": self.data,
            "notification_type": self.notification_type,
            "notification_version": self.notification_version,
        }


class SpaceMembershipRequestPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"
    request_datetime = datetime.now().isoformat()

    def __init__(self, user: User, space: Community, message: Optional[str] = ""):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "space": SpaceData.from_community(space).to_dict(),
                "request_message": message if message else "",
                "request_datetime": self.request_datetime,
                "collaborators_link": f"{settings.APP_URL}/spaces/{space.name}/collaborators/manage?tab=pending&userId={user.id}",
            },
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST.value,
            notification_version=SpaceMembershipRequestPayload.NOTIFICATION_VERSION,
        )
