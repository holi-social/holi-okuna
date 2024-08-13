import base64
from datetime import datetime
from uuid import UUID

from django.db.models import QuerySet
from icalendar import Calendar, Event

from openbook_auth.models import User
from openbook_common.schema.types import GeolocationPointInput
from openbook_common.tracking import track, TrackingEvent
from openbook_common.utils.model_loaders import get_community_model, get_user_model
from openbook_communities.models import Community
from openbook_notifications.services import NotificationsService
from .checkers import AppointmentChecker
from .repositories import AppointmentRepository, VideoCallLinkRepository, LocationDetailsRepository


class AppointmentService:
    def __init__(self):
        self.repository = AppointmentRepository()
        self.video_call_link_service = VideoCallLinkService()
        self.location_service = LocationDetailsService()
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
        geolocation=None,
        location_details=None,
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

        # TODO: Replace it with create_location_details once the application no longer supports deprecated location and geolocation fields.
        location_details = self._create_location_details(geolocation, location, location_details)

        appointment = self.repository.create_appointment(
            title=title,
            invite_only=invite_only,
            participants=participants,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            location=location,
            geolocation=GeolocationPointInput.to_point(geolocation),
            location_details=location_details,
            video_call_link=video_call_link,
            description=description,
            thumbnail=thumbnail,
            permission=permission,
            space=space,
            creator=creator,
        )

        track(
            creator,
            TrackingEvent("appointmentCreated", {"spaceId": str(space_id), "appointmentId": str(appointment.id)}),
        )

        if appointment.ends_in_future:
            recipients = self.determine_recipients(invite_only, participants, space, creator)

            NotificationsService.send_space_appointment_creation_notification(
                space=space,
                appointment=appointment,
                recipients=recipients,
            )

        return appointment

    # TODO: This function is here just for backward compatibility purposes. Remove it once the application no longer supports deprecated location and geolocation fields.
    def _create_location_details(self, geolocation, location, location_details):
        if location_details:
            location_details = self.location_service.create_location_details(location_details)

        elif location and geolocation:
            location_details = self.location_service.create_location_details(
                {
                    "complete_address": location,
                    "city": None,
                    "state": None,
                    "country": [part.strip() for part in location.split(",")][-1],
                    "geolocation": geolocation,
                }
            )

        return location_details

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
        location_details=None,
        video_call_link=None,
        video_call_info=None,
        description=None,
        thumbnail=None,
        remove_thumbnail=False,
    ):
        appointment = self.repository.get_appointment(id_or_slug=str(appointment_id))
        self.checker.check_can_update_appointment(user=user, appointment=appointment)

        current_location = appointment.location_details.complete_address if appointment.location_details else None
        current_start_date_time = appointment.start_date_time
        current_end_date_time = appointment.end_date_time

        user_model = get_user_model()
        participants = user_model.objects.filter(username__in=participant_ids) if participant_ids else []

        video_call_link = self._update_video_call_link(appointment, video_call_info, video_call_link)

        # TODO: Replace it with _manage_location_details once the application no longer supports deprecated location and geolocation fields.
        location_details = self._manage_appointment_location_info(appointment, geolocation, location, location_details)

        updated_appointment = self.repository.update_appointment(
            appointment_id=appointment_id,
            title=title,
            invite_only=invite_only,
            participants=participants,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            location=location,
            geolocation=GeolocationPointInput.to_point(geolocation),
            location_details=location_details,
            video_call_link=video_call_link,
            description=description,
            thumbnail=thumbnail,
            remove_thumbnail=remove_thumbnail,
            permission=permission,
        )

        track(
            user,
            TrackingEvent(
                "appointmentUpdated",
                {"spaceId": str(appointment.space.id), "appointmentId": str(appointment_id)},
            ),
        )

        space_model = get_community_model()
        space: Community = space_model.objects.get(id=updated_appointment.space.id)

        updated_location = (
            updated_appointment.location_details.complete_address if updated_appointment.location_details else None
        )

        location_changed = current_location != updated_location
        date_time_changed = (
            current_start_date_time != updated_appointment.start_date_time
            or current_end_date_time != updated_appointment.end_date_time
        )

        if appointment.ends_in_future and (location_changed or date_time_changed):
            recipients = self.determine_recipients(invite_only, participants, space, user)

            NotificationsService.send_space_appointment_update_notification(
                space=space,
                appointment=updated_appointment,
                location_changed=location_changed,
                date_time_changed=date_time_changed,
                recipients=recipients,
            )

        return updated_appointment

    # TODO: This function is here just for backward compatibility purposes. Remove it once the application no longer supports deprecated location and geolocation fields.
    def _manage_appointment_location_info(self, appointment, geolocation, location, location_details):
        if location_details:
            if appointment.location_details:
                location_details = self._manage_location_details(appointment, location_details)
            else:
                location_details = self._create_location_details(geolocation, location, location_details)
        elif location and geolocation:
            location_details = self.location_service.update_location_details(
                location_id=appointment.location_details.id,
                location_details={
                    "complete_address": location,
                    "city": None,
                    "state": None,
                    "country": [part.strip() for part in location.split(",")][-1],
                    "geolocation": geolocation,
                },
            )
        else:
            if appointment.location_details:
                self.location_service.delete_location_details(location_id=appointment.location_details.id)

            location_details = None

        return location_details

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

    def _manage_location_details(self, appointment, location_details):
        appointment_location = appointment.location_details

        if not location_details:
            if appointment_location:
                self.location_service.delete_location_details(location_id=appointment_location.id)
            return None

        if not appointment_location:
            return self.location_service.create_location_details(location_details=location_details)

        return self.location_service.update_location_details(
            location_id=appointment_location.id,
            location_details=location_details,
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

        track(
            user,
            TrackingEvent(
                "appointmentDeleted", {"spaceId": str(appointment.space_id), "appointmentId": str(appointment_id)}
            ),
        )

        space_model = get_community_model()
        space: Community = space_model.objects.get(id=appointment.space.id)

        if appointment.starts_in_future:
            recipients = space.get_staff_and_subscribers()

            # don't notify the creator
            if recipients.contains(user):
                recipients = recipients.exclude(id__exact=user.id)

            NotificationsService.send_space_appointment_deletion_notification(
                space=space,
                appointment=appointment,
                recipients=recipients,
            )

    def exists(self, appointment_id):
        return self.repository.exists(appointment_id=appointment_id)

    def generate_appointment_ics_file(self, user, appointment_id) -> str:
        appointment = self.get_appointment(user=user, id_or_slug=str(appointment_id))

        # Create a Calendar
        cal = Calendar()

        # Create an Event
        event = Event()

        # Set the properties for the event
        event.add("summary", appointment.title)
        event.add("description", appointment.description)
        event.add("dtstart", appointment.start_date_time)
        event.add("dtend", appointment.end_date_time)
        event.add("location", appointment.location_details.complete_address if appointment.location_details else None)
        event.add("uid", f"appointment_{appointment.id}")
        event.add("url", appointment.video_call_link.url if appointment.video_call_link else None)

        # Add the event to the calendar
        cal.add_component(event)

        # Convert the calendar to bytes
        ics_data = cal.to_ical()

        # Encode bytes into base64
        ics_data_encoded = base64.b64encode(ics_data).decode("utf-8")

        return ics_data_encoded


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


class LocationDetailsService:
    def __init__(self):
        self.repository = LocationDetailsRepository()

    def create_location_details(self, location_details):
        return self.repository.create_location_details(
            complete_address=location_details.get("complete_address"),
            city=location_details.get("city"),
            state=location_details.get("state"),
            country=location_details.get("country"),
            geolocation=GeolocationPointInput.to_point(location_details.get("geolocation")),
        )

    def update_location_details(self, location_id, location_details):
        return self.repository.update_location_details(
            location_id=location_id,
            complete_address=location_details.get("complete_address"),
            city=location_details.get("city"),
            state=location_details.get("state"),
            country=location_details.get("country"),
            geolocation=GeolocationPointInput.to_point(location_details.get("geolocation")),
        )

    def delete_location_details(self, location_id):
        return self.repository.delete_location_details(location_id)
