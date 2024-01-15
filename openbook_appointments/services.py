from openbook_common.utils.model_loaders import get_community_model, get_user_model
from .checkers import AppointmentChecker
from .repositories import AppointmentRepository, VideoCallLinkRepository


class AppointmentService:
    def __init__(self):
        self.repository = AppointmentRepository()
        self.video_call_link_service = VideoCallLinkService()
        self.checker = AppointmentChecker()

    def create_appointment(
        self,
        title,
        invite_only,
        start_date_time,
        end_date_time,
        permission,
        space_id,
        creator,
        participant_ids=None,
        location=None,
        geolocation=None,
        video_call_link=None,
        video_call_info=None,
        description=None,
        thumbnail=None,
    ):
        self.checker.check_can_create_appointment(user=creator, space_id=space_id, invite_only=invite_only)

        space_model = get_community_model()
        space = space_model.objects.get(id=space_id)

        user_model = get_user_model()
        participants = user_model.objects.filter(username__in=participant_ids) if participant_ids else []

        video_call_link = (
            self.video_call_link_service.create_video_call_link(url=video_call_link, additional_info=video_call_info)
            if video_call_link
            else None
        )

        return self.repository.create_appointment(
            title=title,
            invite_only=invite_only,
            participants=participants,
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

    def update_appointment(
        self,
        appointment_id,
        user,
        title=None,
        invite_only=None,
        start_date_time=None,
        end_date_time=None,
        permission=None,
        participant_ids=None,
        location=None,
        geolocation=None,
        video_call_link=None,
        video_call_info=None,
        description=None,
        thumbnail=None,
    ):
        appointment = self.repository.get_appointment(id_or_slug=str(appointment_id))
        self.checker.check_can_update_appointment(user=user, appointment=appointment)

        user_model = get_user_model()
        participants = user_model.objects.filter(username__in=participant_ids) if participant_ids else []

        video_call_link = self._update_video_call_link(appointment, video_call_info, video_call_link)

        return self.repository.update_appointment(
            appointment_id=appointment_id,
            title=title,
            invite_only=invite_only,
            participants=participants,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            location=location,
            geolocation=geolocation,
            video_call_link=video_call_link,
            description=description,
            thumbnail=thumbnail,
            permission=permission,
        )

    def _update_video_call_link(self, appointment, video_call_info, video_call_link):
        if not video_call_link and appointment.video_call_link:
            self.video_call_link_service.delete_video_call_link(video_call_link_id=appointment.video_call_link.id)
            return None

        if not appointment.video_call_link:
            return self.video_call_link_service.create_video_call_link(
                url=video_call_link, additional_info=video_call_info
            )

        return self.video_call_link_service.update_video_call_link(
            video_call_link_id=appointment.video_call_link.id,
            url=video_call_link,
            additional_info=video_call_info,
        )

    def get_appointments(
        self,
        user,
        space_id,
        status_type,
    ):
        if user.is_anonymous or not user.is_member_of_community_with_id(space_id):
            return self.repository.get_appointments(space_id=space_id, status_type=status_type, invite_only=False)

        return self.repository.get_appointments(space_id=space_id, status_type=status_type)

    def get_appointment(
        self,
        id_or_slug,
        user,
    ):
        appointment = self.repository.get_appointment(id_or_slug=id_or_slug)
        self.checker.check_can_query_invite_only_appointment(user=user, appointment=appointment)

        return appointment

    def delete_appointment(self, user, appointment_id):
        appointment = self.repository.get_appointment(id_or_slug=str(appointment_id))
        self.checker.check_can_delete_appointment(user=user, appointment=appointment)
        self.repository.delete_appointment(appointment_id=appointment_id)

    def exists(self, appointment_id):
        return self.repository.exists(appointment_id=appointment_id)


class VideoCallLinkService:
    def __init__(self):
        self.repository = VideoCallLinkRepository()

    def create_video_call_link(self, url, additional_info=None):
        return self.repository.create_video_call_link(url=url, additional_info=additional_info)

    def update_video_call_link(self, video_call_link_id, url, additional_info=None):
        return self.repository.update_video_call_link(
            video_call_link_id=video_call_link_id, url=url, additional_info=additional_info
        )

    def delete_video_call_link(self, video_call_link_id):
        return self.repository.delete_video_call_link(video_call_link_id=video_call_link_id)
