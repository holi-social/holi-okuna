from django.db.models import Q
from django.utils import timezone

from .enums import StatusType
from .models import Appointment, VideoCallLink


class AppointmentRepository:
    def create_appointment(
        self,
        title,
        invite_only,
        start_date_time,
        end_date_time,
        location,
        geolocation,
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


class VideoCallLinkRepository:
    def create_video_call_link(self, url, additional_info=None):
        return VideoCallLink.objects.create(url=url, additional_info=additional_info)
