from datetime import datetime
from uuid import UUID

from django.db.models import QuerySet

from openbook_auth.models import User
from openbook_common.schema.types import GeolocationPointInput
from openbook_common.utils.model_loaders import get_community_model, get_user_model
from openbook_communities.models import Community
from openbook_notifications.notifications import Notifications
from .checkers import AppointmentChecker
from .repositories import AppointmentRepository, VideoCallLinkRepository, LocationRepository


class AppointmentService:
    def __init__(self):
        self.repository = AppointmentRepository()
        self.video_call_link_service = VideoCallLinkService()
        self.location_service = LocationService()
        self.checker = AppointmentChecker()

    def create_appointment(
        self,
        title: str,
        invite_only: bool,
        start_date_time: datetime,
        end_date_time: datetime,
        permission: str,
        space_id: UUID,
        creator: User,
        participant_ids=None,
        location=None,
        video_call_link=None,
        video_call_info=None,
        description=None,
        thumbnail=None,
    ):
        self.checker.check_can_create_appointment(user=creator, space_id=space_id, invite_only=invite_only)

        space_model = get_community_model()
        space: Community = space_model.objects.get(id=space_id)

        user_model = get_user_model()

        participants = (
            user_model.objects.filter(username__in=participant_ids) if participant_ids else User.objects.none()
        )

        video_call_link = (
            self.video_call_link_service.create_video_call_link(url=video_call_link, additional_info=video_call_info)
            if video_call_link
            else None
        )

        location = self.location_service.create_location(location) if location else None

        appointment = self.repository.create_appointment(
            title=title,
            invite_only=invite_only,
            participants=participants,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            location=location,
            video_call_link=video_call_link,
            description=description,
            thumbnail=thumbnail,
            permission=permission,
            space=space,
            creator=creator,
        )

        if appointment.ends_in_future:
            recipients = self.determine_recipients(invite_only, participants, space, creator)

            Notifications.send_space_appointment_creation_notification(
                space=space,
                appointment=appointment,
                recipients=recipients,
            )

        return appointment

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
        video_call_link=None,
        video_call_info=None,
        description=None,
        thumbnail=None,
        remove_thumbnail=False,
    ):
        appointment = self.repository.get_appointment(id_or_slug=str(appointment_id))
        self.checker.check_can_update_appointment(user=user, appointment=appointment)

        user_model = get_user_model()
        participants = user_model.objects.filter(username__in=participant_ids) if participant_ids else []

        video_call_link = self._update_video_call_link(appointment, video_call_info, video_call_link)
        location = self._update_location(appointment, location)

        updated_appointment = self.repository.update_appointment(
            appointment_id=appointment_id,
            title=title,
            invite_only=invite_only,
            participants=participants,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            location=location,
            video_call_link=video_call_link,
            description=description,
            thumbnail=thumbnail,
            remove_thumbnail=remove_thumbnail,
            permission=permission,
        )

        space_model = get_community_model()
        space: Community = space_model.objects.get(id=updated_appointment.space.id)

        if appointment.ends_in_future:
            recipients = self.determine_recipients(invite_only, participants, space, user)

            Notifications.send_space_appointment_update_notification(
                space=space,
                appointment=appointment,
                recipients=recipients,
            )

        return updated_appointment

    def determine_recipients(self, invite_only, participants: QuerySet[User], space: Community, user: User):
        if invite_only:
            # private
            recipients = participants
        else:
            # public
            recipients = space.get_staff_and_subscribers()

        # don't notify the creator
        if recipients.contains(user):
            recipients = recipients.exclude(id__exact=user.id)

        return recipients

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

    def _update_location(self, appointment, location_data):
        appointment_location = appointment.location

        if not location_data:
            if appointment_location:
                self.location_service.delete_location(location_id=appointment_location.id)
            return None

        if not appointment_location:
            return self.location_service.create_location(location_data=location_data)

        return self.location_service.update_location(
            location_id=appointment_location.id,
            location_data=location_data,
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

        space_model = get_community_model()
        space: Community = space_model.objects.get(id=appointment.space.id)

        if appointment.starts_in_future:
            recipients = space.get_staff_and_subscribers()

            # don't notify the creator
            if recipients.contains(user):
                recipients = recipients.exclude(id__exact=user.id)

            Notifications.send_space_appointment_deletion_notification(
                space=space,
                appointment=appointment,
                recipients=recipients,
            )

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


class LocationService:
    def __init__(self):
        self.repository = LocationRepository()

    def create_location(self, location_data):
        return self.repository.create_location(
            complete_address=location_data.get("complete_address"),
            city=location_data.get("city"),
            state=location_data.get("state"),
            country=location_data.get("country"),
            geolocation=GeolocationPointInput.to_point(location_data.get("geolocation")),
        )

    def update_location(self, location_id, location_data):
        return self.repository.update_location(
            location_id=location_id,
            complete_address=location_data.get("complete_address"),
            city=location_data.get("city"),
            state=location_data.get("state"),
            country=location_data.get("country"),
            geolocation=GeolocationPointInput.to_point(location_data.get("geolocation")),
        )

    def delete_location(self, location_id):
        return self.repository.delete_location(location_id)
