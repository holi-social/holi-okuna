import unittest
from unittest.mock import Mock

import pytest

from openbook_appointments.checkers import AppointmentChecker
from openbook_appointments.models import VideoCallLink
from openbook_appointments.repositories import AppointmentRepository
from openbook_appointments.services import VideoCallLinkService, LocationDetailsService, AppointmentService
from openbook_appointments.tests.helpers import make_appointment
from openbook_common.tests.helpers import make_user


class AlwaysSucceedsAppointmentChecker(AppointmentChecker):
    def check_can_create_appointment(self, user, invite_only, space_id):
        return

    def check_can_query_invite_only_appointment(self, user, appointment):
        return

    def check_can_delete_appointment(self, user, appointment):
        return

    def check_can_update_appointment(self, user, appointment):
        return


@pytest.mark.django_db
class AppointmentServiceTestCase(unittest.TestCase):
    repo: AppointmentRepository | Mock
    video_call_link_service: VideoCallLinkService | Mock
    location_service: LocationDetailsService | Mock
    checker: AlwaysSucceedsAppointmentChecker

    service: AppointmentService

    def setUp(self):
        self.repo = Mock(spec=AppointmentRepository)
        self.video_call_link_service = Mock(spec=VideoCallLinkService)
        self.location_service = Mock(spec=LocationDetailsService)
        self.checker = AlwaysSucceedsAppointmentChecker()

        self.service = AppointmentService(self.repo, self.video_call_link_service, self.location_service, self.checker)

    def test_updating_appointment_creates_new_video_call_link(self):
        """
        Test that a new video call link is created if the appointment doesn't already
        have one, and a new link is provided in the input.
        """

        # Given
        user = make_user()
        existing_appointment = make_appointment(video_call_link=None, creator=user)

        self.repo.get_appointment.return_value = existing_appointment
        self.repo.update_appointment.return_value = existing_appointment

        new_video_call_link_url = "https://meet.holi.social/test"
        new_video_call_info = "please join here"

        new_video_call_link = VideoCallLink(
            url=new_video_call_link_url,
            additional_info=new_video_call_info,
        )

        self.video_call_link_service.create_video_call_link.return_value = new_video_call_link

        # When
        self.service.update_appointment(
            appointment_id=existing_appointment.id,
            user=user,
            video_call_link=new_video_call_link_url,
            video_call_info=new_video_call_info,
        )

        # Then
        self.video_call_link_service.create_video_call_link.assert_called_once()
        self.repo.update_appointment.assert_called_once()

    def test_updating_appointment_updates_video_call_link(self):
        """
        Test that video call link is updated if appointment already has one,
        and a new link is provided in the input.
        """

        # Given
        user = make_user()
        existing_video_call_link = VideoCallLink(
            url="https://meet.holi.social/old-link",
        )
        existing_video_call_link.save()

        existing_appointment = make_appointment(video_call_link=existing_video_call_link, creator=user)

        self.repo.get_appointment.return_value = existing_appointment
        self.repo.update_appointment.return_value = existing_appointment

        new_video_call_link_url = "https://meet.holi.social/test"
        new_video_call_info = "please join here"

        new_video_call_link = VideoCallLink(
            url=new_video_call_link_url,
            additional_info=new_video_call_info,
        )

        self.video_call_link_service.update_video_call_link.return_value = new_video_call_link

        # When
        self.service.update_appointment(
            appointment_id=existing_appointment.id,
            user=user,
            video_call_link=new_video_call_link_url,
            video_call_info=new_video_call_info,
        )

        # Then
        self.video_call_link_service.update_video_call_link.assert_called_once_with(
            video_call_link_id=existing_video_call_link.id,
            url=new_video_call_link_url,
            additional_info=new_video_call_info,
        )
        self.repo.update_appointment.assert_called_once()

    def test_updating_appointment_deletes_video_call_link(self):
        # Given
        user = make_user()
        existing_video_call_link = VideoCallLink(
            url="https://meet.holi.social/old-link",
        )
        existing_video_call_link.save()

        existing_appointment = make_appointment(video_call_link=existing_video_call_link, creator=user)

        self.repo.get_appointment.return_value = existing_appointment
        self.repo.update_appointment.return_value = existing_appointment

        new_video_call_link_url = None
        new_video_call_info = None

        self.video_call_link_service.delete_video_call_link.return_value = 1

        # When
        self.service.update_appointment(
            appointment_id=existing_appointment.id,
            user=user,
            video_call_link=new_video_call_link_url,
            video_call_info=new_video_call_info,
        )

        # Then
        self.video_call_link_service.delete_video_call_link.assert_called_once_with(
            video_call_link_id=existing_video_call_link.id,
        )

        self.repo.update_appointment.assert_called_once()
        self.assertIsNone(self.repo.update_appointment.call_args.kwargs["video_call_link"])

    def test_updating_appointmnet_doesnt_touch_video_call_link(self):
        """
        Test that nothing happens to the video call link if the appointment doesn't
        have one, and none is provided in the input.
        """

        # Given
        user = make_user()
        existing_appointment = make_appointment(video_call_link=None, creator=user)

        self.repo.get_appointment.return_value = existing_appointment
        self.repo.update_appointment.return_value = existing_appointment

        # When
        self.service.update_appointment(
            appointment_id=existing_appointment.id,
            user=user,
            video_call_link=None,
            video_call_info=None,
        )

        # Then
        self.video_call_link_service.create_video_call_link.assert_not_called()
        self.video_call_link_service.delete_video_call_link.assert_not_called()
        self.video_call_link_service.update_video_call_link.assert_not_called()

        self.repo.update_appointment.assert_called_once()
        self.assertIsNone(self.repo.update_appointment.call_args.kwargs["video_call_link"])


if __name__ == "__main__":
    unittest.main()
