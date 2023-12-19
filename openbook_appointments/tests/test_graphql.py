from datetime import datetime

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

import logging
from unittest.mock import patch

import pytest
import pytz

from faker import Faker
from django.test import AsyncClient, TestCase

from openbook import settings
from openbook_appointments.enums import PermissionType, StatusType
from openbook_appointments.tests.helpers import create_appointment, appointments
from openbook_common.tests.helpers import (
    make_community,
    make_user,
)

logger = logging.getLogger(__name__)
fake = Faker()
tz = pytz.timezone("Europe/Amsterdam")


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.mark.django_db
class TestAppointments(TestCase):
    mock_current_datetime = timezone.datetime(2024, 1, 1, 12, 0, 0)

    @classmethod
    def setUpTestData(cls):
        cls.user_member = make_user()
        cls.admin = make_user()
        cls.participant = make_user()
        cls.external_member = make_user()

        cls.space = make_community()
        cls.space.add_member(cls.admin)
        cls.space.add_member(cls.user_member)
        cls.space.add_member(cls.participant)
        cls.space.add_administrator(cls.admin)

        cls.public_appointment_input_data = {
            "spaceId": str(cls.space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": False,
            "participantIds": [],
            "startDateTime": fake.future_datetime().isoformat(),
            "endDateTime": fake.future_datetime().isoformat(),
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.ADMINS,
            "videoCallLink": "https://zoom.us/j/712889134",
            "videoCallInfo": fake.text(max_nb_chars=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH),
        }

        cls.invite_only_appointment_input_data = {
            "spaceId": str(cls.space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": True,
            "participantIds": [str(cls.participant.username)],
            "startDateTime": fake.future_datetime().isoformat(),
            "endDateTime": fake.future_datetime().isoformat(),
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.ADMINS,
            "videoCallLink": "https://zoom.us/j/615887136",
            "videoCallInfo": fake.text(max_nb_chars=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH),
        }

        cls.past_appointment_input_data = {
            "spaceId": str(cls.space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": True,
            "participantIds": [],
            "startDateTime": "2023-12-02T08:00:00",
            "endDateTime": "2023-12-02T10:00:00",
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.ADMINS,
            "videoCallLink": "https://zoom.us/j/712889134",
            "videoCallInfo": fake.text(max_nb_chars=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH),
        }

        cls.upcoming_appointment_input_data = {
            "spaceId": str(cls.space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": False,
            "participantIds": [],
            "startDateTime": "2024-01-02T08:00:00",
            "endDateTime": "2024-01-02T10:00:00",
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.ADMINS,
            "videoCallLink": "https://zoom.us/j/712889134",
            "videoCallInfo": fake.text(max_nb_chars=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH),
        }

    def test_can_not_create_appointment_if_not_admin_or_member(self):
        response = create_appointment(self.external_member, self.public_appointment_input_data)

        assert response.errors is not None
        assert response.data is None

        assert (
            "You cannot create an appointment for a space you are not a member of"
            in response.errors[0].extensions["errors"]
        )

    def test_can_create_public_appointment_if_admin(self):
        response = create_appointment(self.admin, self.public_appointment_input_data)

        data = response.data["createAppointment"]

        expected_start_date_time = tz.localize(
            datetime.fromisoformat(self.public_appointment_input_data["startDateTime"])
        ).isoformat()
        expected_end_date_time = tz.localize(
            datetime.fromisoformat(self.public_appointment_input_data["endDateTime"])
        ).isoformat()

        assert data["title"] == self.public_appointment_input_data["title"]
        assert not data["inviteOnly"]
        assert data["participants"] == []
        assert data["startDateTime"] == expected_start_date_time
        assert data["endDateTime"] == expected_end_date_time
        assert data["location"] == self.public_appointment_input_data["location"]
        assert data["description"] == self.public_appointment_input_data["description"]
        assert data["permission"] == self.public_appointment_input_data["permission"]
        assert data["videoCallLink"]["url"] == self.public_appointment_input_data["videoCallLink"]
        assert data["videoCallLink"]["additionalInfo"] == self.public_appointment_input_data["videoCallInfo"]
        assert data["creator"]["fullName"] == self.admin.profile.full_name()

    def test_can_create_invite_only_appointment_if_admin(self):

        response = create_appointment(self.admin, self.invite_only_appointment_input_data)

        data = response.data["createAppointment"]

        expected_start_date_time = tz.localize(
            datetime.fromisoformat(self.invite_only_appointment_input_data["startDateTime"])
        ).isoformat()
        expected_end_date_time = tz.localize(
            datetime.fromisoformat(self.invite_only_appointment_input_data["endDateTime"])
        ).isoformat()

        assert data["title"] == self.invite_only_appointment_input_data["title"]
        assert data["inviteOnly"]
        assert data["participants"] == [{"fullName": self.participant.profile.full_name()}]
        assert data["startDateTime"] == expected_start_date_time
        assert data["endDateTime"] == expected_end_date_time
        assert data["location"] == self.invite_only_appointment_input_data["location"]
        assert data["description"] == self.invite_only_appointment_input_data["description"]
        assert data["permission"] == self.invite_only_appointment_input_data["permission"]
        assert data["videoCallLink"]["url"] == self.invite_only_appointment_input_data["videoCallLink"]
        assert data["videoCallLink"]["additionalInfo"] == self.invite_only_appointment_input_data["videoCallInfo"]
        assert data["creator"]["fullName"] == self.admin.profile.full_name()

    def test_can_not_create_public_appointment_if_member(self):
        response = create_appointment(self.user_member, self.public_appointment_input_data)

        assert response.errors is not None
        assert response.data is None

        assert (
            "You cannot create a public appointment if you are not an administrator of a space"
            in response.errors[0].extensions["errors"]
        )

    def test_can_create_invite_only_appointment_if_member(self):
        response = create_appointment(self.user_member, self.invite_only_appointment_input_data)

        data = response.data["createAppointment"]

        expected_start_date_time = tz.localize(
            datetime.fromisoformat(self.invite_only_appointment_input_data["startDateTime"])
        ).isoformat()
        expected_end_date_time = tz.localize(
            datetime.fromisoformat(self.invite_only_appointment_input_data["endDateTime"])
        ).isoformat()

        assert data["title"] == self.invite_only_appointment_input_data["title"]
        assert data["inviteOnly"]
        assert data["participants"] == [{"fullName": self.participant.profile.full_name()}]
        assert data["startDateTime"] == expected_start_date_time
        assert data["endDateTime"] == expected_end_date_time
        assert data["location"] == self.invite_only_appointment_input_data["location"]
        assert data["description"] == self.invite_only_appointment_input_data["description"]
        assert data["permission"] == self.invite_only_appointment_input_data["permission"]
        assert data["videoCallLink"]["url"] == self.invite_only_appointment_input_data["videoCallLink"]
        assert data["videoCallLink"]["additionalInfo"] == self.invite_only_appointment_input_data["videoCallInfo"]
        assert data["creator"]["fullName"] == self.user_member.profile.full_name()

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_can_query_all_appointments_if_admin(self, mock_current_datetime):
        create_appointment(self.admin, self.past_appointment_input_data)
        create_appointment(self.admin, self.upcoming_appointment_input_data)

        upcoming_appointments_response = appointments(
            user=self.admin, space_id=self.space.id, status_type=StatusType.UPCOMING
        )
        assert upcoming_appointments_response.errors is None
        assert upcoming_appointments_response.data["appointments"]["totalResults"] == 1

        past_appointments_response = appointments(user=self.admin, space_id=self.space.id, status_type=StatusType.PAST)
        assert past_appointments_response.errors is None
        assert past_appointments_response.data["appointments"]["totalResults"] == 1

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_can_query_all_appointments_if_member(self, mock_current_datetime):
        create_appointment(self.admin, self.past_appointment_input_data)
        create_appointment(self.admin, self.upcoming_appointment_input_data)

        upcoming_appointments_response = appointments(
            user=self.user_member, space_id=self.space.id, status_type=StatusType.UPCOMING
        )
        assert upcoming_appointments_response.errors is None
        assert upcoming_appointments_response.data["appointments"]["totalResults"] == 1

        past_appointments_response = appointments(
            user=self.user_member, space_id=self.space.id, status_type=StatusType.PAST
        )
        assert past_appointments_response.errors is None
        assert past_appointments_response.data["appointments"]["totalResults"] == 1

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_can_not_query_invite_only_appointments_if_not_member(self, mock_current_datetime):
        create_appointment(self.admin, self.past_appointment_input_data)
        create_appointment(self.admin, self.upcoming_appointment_input_data)

        upcoming_appointments_response = appointments(
            user=self.external_member, space_id=self.space.id, status_type=StatusType.UPCOMING
        )
        assert upcoming_appointments_response.errors is None
        assert upcoming_appointments_response.data["appointments"]["totalResults"] == 1

        past_appointments_response = appointments(
            user=self.external_member, space_id=self.space.id, status_type=StatusType.PAST
        )
        assert past_appointments_response.errors is None
        assert past_appointments_response.data["appointments"]["totalResults"] == 0

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_can_not_query_invite_only_appointments_if_anonymous(self, mock_current_datetime):
        create_appointment(self.admin, self.past_appointment_input_data)
        create_appointment(self.admin, self.upcoming_appointment_input_data)

        upcoming_appointments_response = appointments(
            user=AnonymousUser, space_id=self.space.id, status_type=StatusType.UPCOMING
        )

        assert upcoming_appointments_response.errors is None
        assert upcoming_appointments_response.data["appointments"]["totalResults"] == 1

        past_appointments_response = appointments(
            user=AnonymousUser, space_id=self.space.id, status_type=StatusType.PAST
        )
        assert past_appointments_response.errors is None
        assert past_appointments_response.data["appointments"]["totalResults"] == 0
