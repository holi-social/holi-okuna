import logging
import uuid
from typing import List, Optional, TYPE_CHECKING

import strawberry
import strawberry_django
from django.db.models import TextChoices
from strawberry.file_uploads import Upload

from openbook_auth.models import User as UserModel
from openbook_auth.models import UserConnectionStatus
from openbook_common.schema.types import GeoJSONInput, GeolocationPoint
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
    interests: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    sdgs: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    skills: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET


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

    # TODO: Only for temporary backwards compatibility, replace by GeoJSON in HOLI-4353 (see below)
    @strawberry_django.field(deprecation_reason="Type change to GeoJSON planned, deprecated since version 1.0.16")
    def geolocation(self) -> Optional[GeolocationPoint]:
        return None

    @strawberry_django.field(select_related=["profile"])
    def geolocation_id(self) -> Optional[str]:
        return self.profile.geolocation_id

    @strawberry_django.field(select_related=["profile"])
    def engagement_level(self) -> Optional[str]:
        return self.profile.engagement_level

    @strawberry_django.field(select_related=["profile__interests"])
    def interests(self) -> List[Optional[Topic]]:
        return self.profile.interests.all()

    @strawberry_django.field(select_related=["profile__sdgs"])
    def sdgs(self) -> List[Optional[SDG]]:
        return self.profile.sdgs.all().order_by("number")

    @strawberry_django.field(select_related=["profile__skills"])
    def skills(self) -> List[Optional[Skill]]:
        return self.profile.skills.all()

    @strawberry_django.field()
    def connection_status_to_myself(self, info) -> Optional[UserConnectionStatus]:
        if info.context.request.user.is_anonymous:
            return None
        return info.context.request.user.get_connection_status_with_user_id(user_id=self.id)

    @strawberry_django.field()
    def connection_status_to_space(self, info, space_id: uuid.UUID) -> List[Optional[SpaceUserConnectionType]]:
        space = CommunityModel.objects.get(id=space_id)
        return space.connection_status_to_user(self)


@strawberry.input
class RegisterDeviceInput:
    token: str
    device_type: Device.DeviceType


@strawberry.enum
class BookmarkType(TextChoices):
    INSIGHT = ("insight",)
    QUOTE = ("quote",)
    RECOMMENDATION = ("recommendation",)
    INITIATIVE = ("initiative",)
