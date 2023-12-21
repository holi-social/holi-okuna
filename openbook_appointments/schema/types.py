import uuid
from typing import List, Optional

import strawberry
import strawberry_django
from strawberry.file_uploads import Upload

from openbook_appointments.enums import PermissionType
from openbook_appointments.models import Appointment, VideoCallLink
from openbook_auth.schema.types import User
from openbook_common.schema.types import GeolocationPoint, GeolocationPointInput


@strawberry_django.type(VideoCallLink)
class VideoCallLink:
    id: strawberry.auto
    url: str
    additional_info: strawberry.auto


@strawberry_django.type(Appointment)
class Appointment:
    id: strawberry.auto
    title: strawberry.auto
    slug: strawberry.auto
    invite_only: strawberry.auto
    participants: Optional[List[User]]
    start_date_time: strawberry.auto
    end_date_time: strawberry.auto
    video_call_link: Optional[VideoCallLink]
    description: strawberry.auto
    thumbnail: Optional[str]
    thumbnail_blurhash: Optional[str]
    permission: PermissionType
    creator: User

    @strawberry_django.field()
    def location(self, info) -> Optional[str]:
        user = info.context.request.user
        if user.is_anonymous:
            return None

        return self.location

    @strawberry_django.field()
    def geolocation(self) -> Optional[GeolocationPoint]:
        return GeolocationPoint.from_point(self.geolocation)

    @strawberry_django.field()
    def video_call_link(self, info) -> Optional[VideoCallLink]:
        user = info.context.request.user
        if user.is_anonymous:
            return None

        return self.video_call_link


@strawberry.input
class CreateAppointmentInput:
    space_id: uuid.UUID
    title: str
    invite_only: bool
    participant_ids: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    start_date_time: str
    end_date_time: str
    location: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    permission: PermissionType
    video_call_link: Optional[str] = strawberry.UNSET
    video_call_info: Optional[str] = strawberry.UNSET
    thumbnail: Optional[Upload] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET


@strawberry.input
class CreateVideoCallLinkInput:
    url: str
    additional_info: Optional[str] = strawberry.UNSET
