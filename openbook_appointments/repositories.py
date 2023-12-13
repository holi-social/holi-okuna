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


class VideoCallLinkRepository:
    def create_video_call_link(self, url, additional_info=None):
        return VideoCallLink.objects.create(url=url, additional_info=additional_info)
