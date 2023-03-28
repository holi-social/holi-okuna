import uuid
from enum import Enum
from typing import List, Optional

from strawberry_django_plus import gql

from openbook_auth import models as auth_models
from openbook_common.schema import types as common_types
from openbook_terms import models as terms_models


@gql.django.type(terms_models.Topic)
class Topic:
    id: gql.auto
    title: gql.auto
    slug: gql.auto
    is_discover_spaces_default: gql.auto


@gql.django.type(terms_models.SDG)
class SDG:
    id: gql.auto
    title: gql.auto
    slug: gql.auto
    number: gql.auto


@gql.django.type(terms_models.Skill)
class Skill:
    id: gql.auto
    title: gql.auto
    slug: gql.auto


@gql.enum
class UpdateConnectionAction(Enum):
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"


@gql.django.type(auth_models.User)
class User:
    id: uuid.UUID = gql.django.field(field_name="username")
    avatar_default_color: str
    avatar_label: str

    @gql.django.field(description="Can be an empty string", select_related=["profile"])
    def full_name(self) -> str:
        return self.profile.full_name

    @gql.django.field(select_related=["profile"])
    def avatar(self) -> Optional[str]:
        return self.profile.avatar

    @gql.django.field(select_related=["profile"])
    def first_name(self) -> Optional[str]:
        return self.profile.name

    @gql.django.field(select_related=["profile"])
    def last_name(self) -> Optional[str]:
        return self.profile.last_name

    @gql.django.field(select_related=["profile"])
    def about_me(self) -> Optional[str]:
        return self.profile.about_me

    @gql.django.field(select_related=["profile"])
    def pronouns(self) -> Optional[str]:
        return self.profile.pronouns

    @gql.django.field(select_related=["profile"])
    def location(self) -> Optional[str]:
        return self.profile.location

    @gql.django.field(select_related=["profile"])
    def geolocation(self) -> Optional[common_types.Geolocation]:
        return common_types.Geolocation.from_point(self.profile.geolocation)

    @gql.django.field(select_related=["profile"])
    def engagement_level(self) -> Optional[str]:
        return self.profile.engagement_level

    @gql.django.field(select_related=["profile__interests"])
    def interests(self) -> List[Optional[Topic]]:
        return self.profile.interests

    @gql.django.field(select_related=["profile__sdgs"])
    def sdgs(self) -> List[Optional[SDG]]:
        return self.profile.sdgs.order_by("number")

    @gql.django.field(select_related=["profile__skills"])
    def skills(self) -> List[Optional[Skill]]:
        return self.profile.skills

    @gql.django.field
    def connection_status_to_myself(self, info) -> Optional[auth_models.UserConnectionStatus]:
        if info.context.request.user.is_anonymous:
            return None
        return info.context.request.user.get_connection_status_with_user_id(user_id=self.id)
