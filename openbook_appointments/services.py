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

    def get_appointments(
        self,
        user,
        space_id,
        status_type,
    ):
        if user.is_anonymous or not user.is_member_of_community_with_id(space_id):
            return self.repository.get_appointments(space_id=space_id, status_type=status_type, invite_only=False)

        return self.repository.get_appointments(space_id=space_id, status_type=status_type)


class VideoCallLinkService:
    def __init__(self):
        self.repository = VideoCallLinkRepository()

    def create_video_call_link(self, url, additional_info=None):
        return self.repository.create_video_call_link(url=url, additional_info=additional_info)
