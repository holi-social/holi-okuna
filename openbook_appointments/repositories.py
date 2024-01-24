from typing import Optional
from uuid import UUID

from django.db.models import Q
from django.utils import timezone

from openbook_common.utils.helpers import is_uuid
from .enums import StatusType
from .models import Appointment, VideoCallLink, LocationDetails


class AppointmentRepository:
    def create_appointment(
        self,
        title,
        invite_only,
        start_date_time,
        end_date_time,
        location,
        geolocation,
        location_details,
        video_call_link,
        description,
        thumbnail,
        permission,
        space,
        creator,
        participants,
    ):
        appointment = Appointment.objects.create(
            title=title,
            invite_only=invite_only,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            location=location,
            geolocation=geolocation,
            location_details=location_details,
            video_call_link=video_call_link,
            description=description,
            thumbnail=thumbnail,
            permission=permission,
            space=space,
            creator=creator,
        )

        appointment.participants.set(participants)

        return appointment

    def get_appointments(self, space_id, status_type, invite_only=None):
        current_datetime = timezone.now()

        query = Q(space__id=space_id)

        if status_type == StatusType.UPCOMING:
            query.add(Q(end_date_time__gte=current_datetime), Q.AND)
        elif status_type == StatusType.PAST:
            query.add(Q(end_date_time__lt=current_datetime), Q.AND)

        if invite_only is not None:
            query.add(Q(invite_only=invite_only), Q.AND)

        appointments = Appointment.objects.filter(query).order_by("start_date_time")

        return appointments

    def update_appointment(
        self,
        appointment_id,
        title=None,
        invite_only=None,
        start_date_time=None,
        end_date_time=None,
        location=None,
        geolocation=None,
        location_details=None,
        video_call_link=None,
        description=None,
        thumbnail=None,
        remove_thumbnail=False,
        permission=None,
        participants=None,
    ):
        appointment = Appointment.objects.get(id=appointment_id)

        if title is not None:
            appointment.title = title

        if invite_only is not None:
            appointment.invite_only = invite_only

        if start_date_time is not None:
            appointment.start_date_time = start_date_time

        if end_date_time is not None:
            appointment.end_date_time = end_date_time

        if location is not None:
            appointment.location = location

        if geolocation is not None:
            appointment.geolocation = geolocation

        if location_details is not None:
            appointment.location_details = location_details

        if video_call_link is not None:
            appointment.video_call_link = video_call_link

        if description is not None:
            appointment.description = description

        if remove_thumbnail:
            appointment.delete_thumbnail()
        elif thumbnail:
            appointment.update_thumbnail(thumbnail)

        if permission is not None:
            appointment.permission = permission

        if participants is not None:
            appointment.participants.set(participants)

        appointment.save()

        return appointment

    def get_appointment(self, id_or_slug):
        if is_uuid(id_or_slug):
            return Appointment.objects.get(id=id_or_slug)
        return Appointment.objects.get(slug=id_or_slug)

    def delete_appointment(self, appointment_id):
        Appointment.objects.get(id=appointment_id).delete()

    def exists(self, appointment_id):
        return Appointment.objects.filter(id=appointment_id).exists()


class VideoCallLinkRepository:
    def create_video_call_link(self, url, additional_info=None):
        return VideoCallLink.objects.create(url=url, additional_info=additional_info)

    def update_video_call_link(self, video_call_link_id: UUID, url: str, additional_info: Optional[str] = None):
        video_call_link = VideoCallLink.objects.get(id=video_call_link_id)
        video_call_link.url = url
        if additional_info is not None:
            video_call_link.additional_info = additional_info
        video_call_link.save()
        return video_call_link

    def delete_video_call_link(self, video_call_link_id):
        VideoCallLink.objects.get(id=video_call_link_id).delete()


class LocationDetailsRepository:
    def create_location_details(self, complete_address, city, state, country, geolocation):
        return LocationDetails.objects.create(
            complete_address=complete_address, city=city, state=state, country=country, geolocation=geolocation
        )

    def update_location_details(self, location_id, complete_address, city, state, country, geolocation):
        location_details = LocationDetails.objects.get(id=location_id)
        location_details.complete_address = complete_address
        location_details.city = city
        location_details.state = state
        location_details.country = country
        location_details.geolocation = geolocation
        location_details.save()
        return location_details

    def delete_location_details(self, location_id):
        return LocationDetails.objects.get(id=location_id).delete()
