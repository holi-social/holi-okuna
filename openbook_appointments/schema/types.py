import uuid
from typing import List, Optional

import strawberry
import strawberry_django
from strawberry.file_uploads import Upload

from openbook_appointments.enums import PermissionType
from openbook_appointments.models import Appointment, VideoCallLink, LocationDetails
from openbook_auth.schema.types import User
from openbook_common.schema.types import GeolocationPoint, GeolocationPointInput


@strawberry_django.type(VideoCallLink)
class VideoCallLink:
    id: strawberry.auto
    url: strawberry.auto
    additional_info: strawberry.auto


@strawberry_django.type(LocationDetails)
class LocationDetails:
    city: strawberry.auto
    state: strawberry.auto
    country: strawberry.auto

    @strawberry_django.field()
    def complete_address(self, info) -> Optional[str]:
        user = info.context.request.user
        if user.is_anonymous:
            if self.city:
                return f"{self.city}, {self.country}"
            if self.state:
                return f"{self.state}, {self.country}"
            return self.country

        return self.complete_address

    @strawberry_django.field()
    def geolocation(self, info) -> Optional[GeolocationPoint]:
        user = info.context.request.user
        if user.is_anonymous:
            return None
        return GeolocationPoint.from_point(self.geolocation)


@strawberry_django.type(Appointment)
class Appointment:
    id: strawberry.auto
    title: strawberry.auto
    slug: strawberry.auto
    invite_only: strawberry.auto
    participants: Optional[List[User]]
    start_date_time: strawberry.auto
    end_date_time: strawberry.auto
    location_details: Optional[LocationDetails]
    video_call_link: Optional[VideoCallLink]
    description: strawberry.auto
    thumbnail: Optional[str]
    thumbnail_blurhash: Optional[str]
    permission: PermissionType
    creator: Optional[User]
    is_hybrid: Optional[bool]
    has_video_call_link: Optional[bool]

    @strawberry_django.field(deprecation_reason="Use `location_details` instead")
    def location(self, info) -> Optional[str]:
        user = info.context.request.user
        if user.is_anonymous:
            return None

        return self.location

    @strawberry_django.field(deprecation_reason="Use `location_details` instead")
    def geolocation(self, info) -> Optional[GeolocationPoint]:
        user = info.context.request.user
        if user.is_anonymous:
            return None

        return GeolocationPoint.from_point(self.geolocation)

    @strawberry_django.field()
    def video_call_link(self, info) -> Optional[VideoCallLink]:
        user = info.context.request.user
        if user.is_anonymous:
            return None

        return self.video_call_link


@strawberry.input
class LocationDetailsInput:
    complete_address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET


@strawberry.input
class CreateAppointmentInput:
    space_id: uuid.UUID
    title: str
    invite_only: bool
    participant_ids: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    start_date_time: str
    end_date_time: str
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    location_details: Optional[LocationDetailsInput] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    permission: PermissionType
    video_call_link: Optional[str] = strawberry.UNSET
    video_call_info: Optional[str] = strawberry.UNSET
    thumbnail: Optional[Upload] = strawberry.UNSET


@strawberry.input
class UpdateAppointmentInput:
    appointment_id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    invite_only: Optional[bool] = strawberry.UNSET
    participant_ids: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    start_date_time: Optional[str] = strawberry.UNSET
    end_date_time: Optional[str] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    location_details: Optional[LocationDetailsInput] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    permission: Optional[PermissionType] = strawberry.UNSET
    video_call_link: Optional[str] = strawberry.UNSET
    video_call_info: Optional[str] = strawberry.UNSET
    thumbnail: Optional[Upload] = strawberry.UNSET


@strawberry.input
class CreateVideoCallLinkInput:
    url: str
    additional_info: Optional[str] = strawberry.UNSET
