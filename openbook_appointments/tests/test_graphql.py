from datetime import datetime

import logging
from unittest import TestCase

import pytest
import pytz

from faker import Faker
from django.test import AsyncClient

from openbook import settings
from openbook_appointments.enums import PermissionType
from openbook_appointments.tests.helpers import create_appointment
from openbook_common.tests.helpers import (
    make_community,
    make_user,
)

logger = logging.getLogger(__name__)
fake = Faker()
timezone = pytz.timezone("Europe/Amsterdam")


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.mark.django_db
class TestAppointments(TestCase):
    def test_can_not_create_appointment_if_not_admin_or_member(self):
        user = make_user()
        space = make_community()

        input_data = {
            "spaceId": str(space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": False,
            "participantIds": [],
            "startDateTime": fake.future_datetime().isoformat(),
            "endDateTime": fake.future_datetime().isoformat(),
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.ADMINS,
            "videoCallLink": "https://zoom.us/j/123456789",
            "videoCallInfo": fake.text(max_nb_chars=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH),
        }

        response = create_appointment(user, input_data)

        assert response.errors is not None
        assert response.data is None

        assert (
            "You cannot create an appointment for a space you are not a member of"
            in response.errors[0].extensions["errors"]
        )

    def test_can_create_public_appointment_if_admin(self):
        user = make_user()
        space = make_community()
        space.add_member(user)

        space.add_administrator(user)

        input_data = {
            "spaceId": str(space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": False,
            "participantIds": [],
            "startDateTime": fake.future_datetime().isoformat(),
            "endDateTime": fake.future_datetime().isoformat(),
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.ADMINS,
            "videoCallLink": "https://zoom.us/j/123456789",
            "videoCallInfo": fake.text(max_nb_chars=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH),
        }

        response = create_appointment(user, input_data)

        data = response.data["createAppointment"]

        expected_start_date_time = timezone.localize(datetime.fromisoformat(input_data["startDateTime"])).isoformat()
        expected_end_date_time = timezone.localize(datetime.fromisoformat(input_data["endDateTime"])).isoformat()

        assert data["title"] == input_data["title"]
        assert not data["inviteOnly"]
        assert data["participants"] == []
        assert data["startDateTime"] == expected_start_date_time
        assert data["endDateTime"] == expected_end_date_time
        assert data["location"] == input_data["location"]
        assert data["description"] == input_data["description"]
        assert data["permission"] == input_data["permission"]
        assert data["videoCallLink"]["url"] == input_data["videoCallLink"]
        assert data["videoCallLink"]["additionalInfo"] == input_data["videoCallInfo"]
        assert data["creator"]["fullName"] == user.profile.full_name()

    def test_can_create_invite_only_appointment_if_admin(self):
        user = make_user()
        participant = make_user()

        space = make_community()
        space.add_member(user)
        space.add_member(participant)

        space.add_administrator(user)

        input_data = {
            "spaceId": str(space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": True,
            "participantIds": [str(participant.username)],
            "startDateTime": fake.future_datetime().isoformat(),
            "endDateTime": fake.future_datetime().isoformat(),
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.ADMINS,
            "videoCallLink": "https://zoom.us/j/123456789",
            "videoCallInfo": fake.text(max_nb_chars=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH),
        }

        response = create_appointment(user, input_data)

        data = response.data["createAppointment"]

        expected_start_date_time = timezone.localize(datetime.fromisoformat(input_data["startDateTime"])).isoformat()
        expected_end_date_time = timezone.localize(datetime.fromisoformat(input_data["endDateTime"])).isoformat()

        assert data["title"] == input_data["title"]
        assert data["inviteOnly"]
        assert data["participants"] == [{"fullName": participant.profile.full_name()}]
        assert data["startDateTime"] == expected_start_date_time
        assert data["endDateTime"] == expected_end_date_time
        assert data["location"] == input_data["location"]
        assert data["description"] == input_data["description"]
        assert data["permission"] == input_data["permission"]
        assert data["videoCallLink"]["url"] == input_data["videoCallLink"]
        assert data["videoCallLink"]["additionalInfo"] == input_data["videoCallInfo"]
        assert data["creator"]["fullName"] == user.profile.full_name()

    def test_can_not_create_public_appointment_if_member(self):
        user = make_user()
        space = make_community()

        space.add_member(user)

        input_data = {
            "spaceId": str(space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": False,
            "participantIds": [],
            "startDateTime": fake.future_datetime().isoformat(),
            "endDateTime": fake.future_datetime().isoformat(),
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.ADMINS,
            "videoCallLink": "https://zoom.us/j/123456789",
            "videoCallInfo": fake.text(max_nb_chars=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH),
        }

        response = create_appointment(user, input_data)

        assert response.errors is not None
        assert response.data is None

        assert (
            "You cannot create a public appointment if you are not an administrator of a space"
            in response.errors[0].extensions["errors"]
        )

    def test_can_create_invite_only_appointment_if_member(self):
        user = make_user()
        participant = make_user()
        space = make_community()

        space.add_member(user)
        space.add_member(participant)

        input_data = {
            "spaceId": str(space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": True,
            "participantIds": [str(participant.username)],
            "startDateTime": fake.future_datetime().isoformat(),
            "endDateTime": fake.future_datetime().isoformat(),
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.ADMINS,
            "videoCallLink": "https://zoom.us/j/123456789",
            "videoCallInfo": fake.text(max_nb_chars=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH),
        }

        response = create_appointment(user, input_data)

        data = response.data["createAppointment"]

        expected_start_date_time = timezone.localize(datetime.fromisoformat(input_data["startDateTime"])).isoformat()
        expected_end_date_time = timezone.localize(datetime.fromisoformat(input_data["endDateTime"])).isoformat()

        assert data["title"] == input_data["title"]
        assert data["inviteOnly"]
        assert data["participants"] == [{"fullName": participant.profile.full_name()}]
        assert data["startDateTime"] == expected_start_date_time
        assert data["endDateTime"] == expected_end_date_time
        assert data["location"] == input_data["location"]
        assert data["description"] == input_data["description"]
        assert data["permission"] == input_data["permission"]
        assert data["videoCallLink"]["url"] == input_data["videoCallLink"]
        assert data["videoCallLink"]["additionalInfo"] == input_data["videoCallInfo"]
        assert data["creator"]["fullName"] == user.profile.full_name()
