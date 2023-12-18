from unittest.mock import patch

import pytest
import logging
from django.test import AsyncClient, TestCase
from django.utils import timezone

from django.contrib.auth.models import AnonymousUser

from openbook_appointments.services import AppointmentService
from openbook_common.tests.helpers import make_user, make_community
from openbook_communities.tests.helpers import get_space_by_id_with_appointments

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.mark.django_db
class TestSpaceAppointments(TestCase):
    mock_current_datetime = timezone.datetime(2024, 6, 14, 12, 0, 0)

    @classmethod
    def setUpTestData(cls):
        cls.anonymous_user = AnonymousUser()
        cls.admin_user = make_user()
        cls.member_user = make_user()
        cls.external_user = make_user()
        cls.space = make_community(creator=cls.admin_user)

        cls.space.add_member(cls.member_user)

        cls.old_public_appointment = AppointmentService().create_appointment(
            space_id=str(cls.space.id),
            title="Public Appointment",
            invite_only=False,
            participant_ids=[],
            start_date_time="2023-12-16T08:00:00",
            end_date_time="2023-12-16T10:00:00",
            location="Hamburg, Germany",
            description="This is an old public appointment",
            permission="ADMINS",
            creator=cls.admin_user,
            video_call_link="https://zoom.us/j/1234666789",
        )

        cls.public_appointment = AppointmentService().create_appointment(
            space_id=str(cls.space.id),
            title="Public Appointment",
            invite_only=False,
            participant_ids=[],
            start_date_time="2024-06-16T08:00:00",
            end_date_time="2024-06-16T10:00:00",
            location="Hamburg, Germany",
            description="This is a public appointment where everybody is welcome",
            permission="ADMINS",
            creator=cls.admin_user,
            video_call_link="https://zoom.us/j/123456789",
        )

        cls.another_public_appointment = AppointmentService().create_appointment(
            space_id=str(cls.space.id),
            title="Public Appointment",
            invite_only=False,
            participant_ids=[],
            start_date_time="2024-06-17T08:00:00",
            end_date_time="2024-06-17T10:00:00",
            location="Hamburg, Germany",
            description="This is a another public appointment where everybody is welcome",
            permission="ADMINS",
            creator=cls.admin_user,
            video_call_link="https://zoom.us/j/144456789",
        )

        cls.invite_only_appointment = AppointmentService().create_appointment(
            space_id=str(cls.space.id),
            title="Public Appointment",
            invite_only=True,
            participant_ids=[],
            start_date_time="2024-06-18T08:00:00",
            end_date_time="2024-06-18T10:00:00",
            location="Munich, Germany",
            description="This is a invite_only appointment where only invited people are welcome",
            permission="PARTICIPANTS",
            creator=cls.admin_user,
            video_call_link="https://zoom.us/j/123456789",
        )

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_can_only_retrieve_upcoming_appointments(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.member_user)
        assert response["appointments"]["totalResults"] == 3
        assert str(self.old_public_appointment.id) not in [
            appointment["id"] for appointment in response["appointments"]["data"]
        ]

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_upcoming_appointments_ordered_chronologically(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.member_user)
        assert response["appointments"]["totalResults"] == 3
        assert response["appointments"]["data"][0]["id"] == str(self.public_appointment.id)
        assert response["appointments"]["data"][1]["id"] == str(self.another_public_appointment.id)
        assert response["appointments"]["data"][2]["id"] == str(self.invite_only_appointment.id)

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_all_users_can_retrieve_all_public_appointments(self, mock_current_datetime):
        # space member
        response = get_space_by_id_with_appointments(self.space.id, self.member_user)
        assert response["appointments"]["totalResults"] == 3  # 2 public + 1 invite_only

        # external user
        response = get_space_by_id_with_appointments(self.space.id, self.external_user)
        assert response["appointments"]["totalResults"] == 2

        # anonymous user
        response = get_space_by_id_with_appointments(self.space.id, AnonymousUser)
        assert response["appointments"]["totalResults"] == 2

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_member_users_can_retrieve_all_appointments_details(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.member_user)
        assert response["appointments"]["totalResults"] == 3
        assert response["appointments"]["data"][0]["location"] == self.public_appointment.location
        assert (
            response["appointments"]["data"][0]["videoCallLink"]["url"] == self.public_appointment.video_call_link.url
        )
        assert response["appointments"]["data"][1]["location"] == self.another_public_appointment.location
        assert (
            response["appointments"]["data"][1]["videoCallLink"]["url"]
            == self.another_public_appointment.video_call_link.url
        )
        assert response["appointments"]["data"][2]["location"] == self.invite_only_appointment.location
        assert (
            response["appointments"]["data"][2]["videoCallLink"]["url"]
            == self.invite_only_appointment.video_call_link.url
        )

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_external_users_can_not_retrieve_invite_only_appointments(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.external_user)
        assert response["appointments"]["totalResults"] == 2
        assert str(self.invite_only_appointment.id) not in [
            appointment["id"] for appointment in response["appointments"]["data"]
        ]

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_external_users_can_retrieve_public_appointments_details(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.external_user)
        assert response["appointments"]["totalResults"] == 2
        assert response["appointments"]["data"][0]["location"] == self.public_appointment.location
        assert (
            response["appointments"]["data"][0]["videoCallLink"]["url"] == self.public_appointment.video_call_link.url
        )
        assert response["appointments"]["data"][1]["location"] == self.another_public_appointment.location
        assert (
            response["appointments"]["data"][1]["videoCallLink"]["url"]
            == self.another_public_appointment.video_call_link.url
        )

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_anonymous_users_can_not_retrieve_invite_only_appointments(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.external_user)
        assert response["appointments"]["totalResults"] == 2
        assert str(self.invite_only_appointment.id) not in [
            appointment["id"] for appointment in response["appointments"]["data"]
        ]

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_anonymous_users_can_not_retrieve_public_appointments_details(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.anonymous_user)
        assert response["appointments"]["totalResults"] == 2
        assert response["appointments"]["data"][0]["location"] is None
        assert response["appointments"]["data"][0]["videoCallLink"] is None
        assert response["appointments"]["data"][1]["location"] is None
        assert response["appointments"]["data"][1]["videoCallLink"] is None
