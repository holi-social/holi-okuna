import logging
import uuid
from typing import List, Optional, TYPE_CHECKING

import strawberry
import strawberry_django

from strawberry.file_uploads import Upload

from openbook_auth.models import User as UserModel, UserRole
from openbook_auth.models import UserConnectionStatus
from openbook_common.schema.types import GeoJSONInput
from openbook_communities.enums import UpdateConnectionAction
from openbook_communities.models import Community as CommunityModel
from openbook_communities.models import SpaceUserConnectionType

from openbook_terms.schema.types import SDG, Skill, Topic
from openbook_devices.models import Device

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@strawberry.input
class UpdateAuthenticatedUserInput:
    avatar: Optional[Upload] = strawberry.UNSET
    first_name: Optional[str] = strawberry.UNSET
    last_name: Optional[str] = strawberry.UNSET
    about_me: Optional[str] = strawberry.UNSET
    pronouns: Optional[str] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeoJSONInput] = strawberry.UNSET
    engagement_level: Optional[str] = strawberry.UNSET
    interests: Optional[List[Optional[uuid.UUID]]] = strawberry_django.field(
        deprecation_reason="Deprecated since 1.52. Use interests_v2 instead."
    )
    interests_v2: Optional[List[str]] = strawberry.UNSET
    sdgs: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    skills: Optional[List[Optional[uuid.UUID]]] = strawberry_django.field(
        deprecation_reason="Deprecated since 1.52. Use skills_v2 instead."
    )
    skills_v2: Optional[List[str]] = strawberry.UNSET
    tracking_consent_analytics: Optional[bool] = strawberry.UNSET
    tracking_consent_personalization: Optional[bool] = strawberry.UNSET


@strawberry.input
class UpdateConnectionWithUserInput:
    user_id: Optional[str] = strawberry.UNSET
    action: UpdateConnectionAction


@strawberry_django.type(UserModel)
class User:
    id: uuid.UUID = strawberry_django.field(field_name="username")
    identity: Optional[str]
    avatar_default_color: str
    avatar_label: str
    role: Optional[UserRole]

    @strawberry_django.field(description="Can be an empty string", select_related=["profile"])
    def full_name(self) -> str:
        return self.profile.full_name

    @strawberry_django.field(select_related=["profile"])
    def avatar(self) -> Optional[str]:
        return self.profile.avatar

    @strawberry_django.field(select_related=["profile"])
    def avatar_blurhash(self) -> Optional[str]:
        return self.profile.avatar_blurhash

    @strawberry_django.field(select_related=["profile"])
    def first_name(self) -> Optional[str]:
        return self.profile.name

    @strawberry_django.field(select_related=["profile"])
    def last_name(self) -> Optional[str]:
        return self.profile.last_name

    @strawberry_django.field(select_related=["profile"])
    def about_me(self) -> Optional[str]:
        return self.profile.about_me

    @strawberry_django.field(select_related=["profile"])
    def pronouns(self) -> Optional[str]:
        return self.profile.pronouns

    @strawberry_django.field(select_related=["profile"])
    def location(self) -> Optional[str]:
        return self.profile.location

    @strawberry_django.field(select_related=["profile"])
    def geolocation_id(self) -> Optional[str]:
        return self.profile.geolocation_id

    @strawberry_django.field(select_related=["profile"])
    def engagement_level(self) -> Optional[str]:
        return self.profile.engagement_level

    @strawberry_django.field(
        select_related=["profile__interests"], deprecation_reason="Deprecated since 1.52. Use interests_v2 instead."
    )
    def interests(self) -> List[Optional[Topic]]:
        return self.profile.interests.all()

    @strawberry_django.field(select_related=["profile"])
    def interests_v2(self) -> List[Optional[str]]:
        return self.profile.interests_v2

    @strawberry_django.field(select_related=["profile__sdgs"])
    def sdgs(self) -> List[Optional[SDG]]:
        return self.profile.sdgs.all().order_by("number")

    @strawberry_django.field(
        select_related=["profile__skills"], deprecation_reason="Deprecated since 1.52. Use skills_v2 instead."
    )
    def skills(self) -> List[Optional[Skill]]:
        return self.profile.skills.all()

    @strawberry_django.field(select_related=["profile"])
    def skills_v2(self) -> List[Optional[str]]:
        return self.profile.skills_v2

    @strawberry_django.field()
    def connection_status_to_myself(self, info) -> Optional[UserConnectionStatus]:
        user = info.context.request.user
        if user.is_anonymous:
            return None
        return user.get_connection_status_with_user_id(user_id=self.id)

    @strawberry_django.field()
    def connection_status_to_space(self, info, space_id: uuid.UUID) -> List[Optional[SpaceUserConnectionType]]:
        space = CommunityModel.objects.get(id=space_id)
        return space.connection_status_to_user(self)


@strawberry_django.type(UserModel)
class AuthenticatedUser(User):
    tracking_consent_analytics: Optional[bool]
    tracking_consent_personalization: Optional[bool]
    is_employee: bool
    is_verified: bool
    role: Optional[UserRole]


@strawberry.input
class RegisterDeviceInput:
    token: str
    device_type: Device.DeviceType
