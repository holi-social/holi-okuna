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
from openbook_appointments.tests.helpers import (
    create_appointment,
    appointments,
    appointment,
    delete_appointment,
    update_appointment,
    update_input_data,
)
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
        cls.another_user_member = make_user()

        cls.space = make_community()
        cls.space.add_member(cls.admin)
        cls.space.add_member(cls.user_member)
        cls.space.add_member(cls.participant)
        cls.space.add_member(cls.another_user_member)
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

        cls.another_invite_only_appointment_input_data = {
            "spaceId": str(cls.space.id),
            "title": fake.text(max_nb_chars=settings.APPOINTMENT_TITLE_MAX_LENGTH),
            "inviteOnly": True,
            "participantIds": [str(cls.participant.username)],
            "startDateTime": fake.future_datetime().isoformat(),
            "endDateTime": fake.future_datetime().isoformat(),
            "location": fake.text(max_nb_chars=settings.APPOINTMENT_LOCATION_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH),
            "permission": PermissionType.PARTICIPANTS,
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
            "You cannot create appointments of a space you are not a member of"
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

    def test_can_not_query_invite_only_appointment_if_anonymous(self):
        mutation_response = create_appointment(self.admin, self.invite_only_appointment_input_data)
        assert mutation_response.errors is None

        appointment_id = mutation_response.data["createAppointment"]["id"]

        query_response = appointment(user=AnonymousUser, id_or_slug=str(appointment_id))

        assert query_response.errors is not None
        assert query_response.data is None

        assert (
            "You cannot query invite only appointments of a space you are not a member of"
            in query_response.errors[0].extensions["errors"]
        )

    def test_can_not_query_invite_only_appointment_if_not_member(self):
        mutation_response = create_appointment(self.admin, self.invite_only_appointment_input_data)
        assert mutation_response.errors is None

        appointment_id = mutation_response.data["createAppointment"]["id"]

        query_response = appointment(user=self.external_member, id_or_slug=str(appointment_id))

        assert query_response.errors is not None
        assert query_response.data is None

        assert (
            "You cannot query invite only appointments of a space you are not a member of"
            in query_response.errors[0].extensions["errors"]
        )

    def test_can_query_public_appointment_if_anonymous(self):
        mutation_response = create_appointment(self.admin, self.public_appointment_input_data)
        assert mutation_response.errors is None

        appointment_id = mutation_response.data["createAppointment"]["id"]

        query_response = appointment(user=AnonymousUser, id_or_slug=str(appointment_id))

        assert query_response.errors is None
        assert query_response.data["appointment"]["id"] == appointment_id

    def test_can_query_public_appointment_if_not_member(self):
        mutation_response = create_appointment(self.admin, self.public_appointment_input_data)
        assert mutation_response.errors is None

        appointment_id = mutation_response.data["createAppointment"]["id"]

        query_response = appointment(user=self.external_member, id_or_slug=str(appointment_id))

        assert query_response.errors is None
        assert query_response.data["appointment"]["id"] == appointment_id

    def test_can_query_appointment_if_admin(self):
        mutation_response = create_appointment(self.admin, self.past_appointment_input_data)
        assert mutation_response.errors is None

        appointment_id = mutation_response.data["createAppointment"]["id"]

        query_response = appointment(user=self.admin, id_or_slug=str(appointment_id))

        assert query_response.errors is None
        assert query_response.data["appointment"]["id"] == appointment_id

    def test_can_query_appointment_if_member(self):
        mutation_response = create_appointment(self.admin, self.upcoming_appointment_input_data)
        assert mutation_response.errors is None

        appointment_id = mutation_response.data["createAppointment"]["id"]

        query_response = appointment(user=self.user_member, id_or_slug=str(appointment_id))

        assert query_response.errors is None
        assert query_response.data["appointment"]["id"] == appointment_id

    def test_can_query_appointment_with_id_or_slug(self):
        mutation_response = create_appointment(self.admin, self.public_appointment_input_data)
        assert mutation_response.errors is None

        appointment_id = mutation_response.data["createAppointment"]["id"]
        appointment_slug = mutation_response.data["createAppointment"]["slug"]

        query_by_id_response = appointment(user=self.user_member, id_or_slug=str(appointment_id))

        assert query_by_id_response.errors is None
        assert query_by_id_response.data["appointment"]["id"] == appointment_id

        query_by_slug_response = appointment(user=self.user_member, id_or_slug=appointment_slug)

        assert query_by_slug_response.errors is None
        assert query_by_slug_response.data["appointment"]["slug"] == appointment_slug

    def test_can_delete_appointment_if_admin(self):
        create_mutation_response = create_appointment(self.user_member, self.invite_only_appointment_input_data)
        assert create_mutation_response.errors is None

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        delete_mutation_response = delete_appointment(user=self.admin, appointment_id=appointment_id)

        assert delete_mutation_response.errors is None
        assert delete_mutation_response.data["deleteAppointment"]["success"] == True

    def test_can_delete_invite_only_appointment_if_creator(self):
        create_mutation_response = create_appointment(self.user_member, self.invite_only_appointment_input_data)
        assert create_mutation_response.errors is None

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        delete_mutation_response = delete_appointment(self.user_member, appointment_id=appointment_id)

        assert delete_mutation_response.errors is None
        assert delete_mutation_response.data["deleteAppointment"]["success"] == True

    def test_can_delete_invite_only_appointment_if_participant(self):
        create_mutation_response = create_appointment(
            self.user_member, self.another_invite_only_appointment_input_data
        )
        assert create_mutation_response.errors is None

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        delete_mutation_response = delete_appointment(self.participant, appointment_id=appointment_id)

        assert delete_mutation_response.errors is None
        assert delete_mutation_response.data["deleteAppointment"]["success"] == True

    def test_can_not_delete_appointment_if_not_member(self):
        create_mutation_response = create_appointment(self.user_member, self.invite_only_appointment_input_data)
        assert create_mutation_response.errors is None

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        delete_mutation_response = delete_appointment(self.external_member, appointment_id=appointment_id)

        assert delete_mutation_response.errors is not None
        assert delete_mutation_response.data is None

        assert (
            "You cannot delete appointments of a space you are not a member of"
            in delete_mutation_response.errors[0].extensions["errors"]
        )

    def test_can_not_delete_appointment_with_admins_permission_if_participant(self):
        create_mutation_response = create_appointment(self.user_member, self.invite_only_appointment_input_data)
        assert create_mutation_response.errors is None

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        delete_mutation_response = delete_appointment(self.participant, appointment_id=appointment_id)

        assert delete_mutation_response.errors is not None
        assert delete_mutation_response.data is None

        assert (
            "You do not have the permission to delete the appointment"
            in delete_mutation_response.errors[0].extensions["errors"]
        )

    def test_can_not_delete_appointment_with_participants_permission_if_not_participant(self):
        create_mutation_response = create_appointment(
            self.user_member, self.another_invite_only_appointment_input_data
        )
        assert create_mutation_response.errors is None

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        delete_mutation_response = delete_appointment(self.another_user_member, appointment_id=appointment_id)

        assert delete_mutation_response.errors is not None
        assert delete_mutation_response.data is None

        assert (
            "You do not have the permission to delete the appointment"
            in delete_mutation_response.errors[0].extensions["errors"]
        )

    def test_can_not_update_appointment_if_not_member(self):
        create_mutation_response = create_appointment(self.user_member, self.invite_only_appointment_input_data)
        assert create_mutation_response.errors is None

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        input_data = update_input_data(
            appointment_id=appointment_id, input_data=self.invite_only_appointment_input_data
        )

        update_mutation_response = update_appointment(self.external_member, input_data)

        assert update_mutation_response.errors is not None
        assert update_mutation_response.data is None

        assert (
            "You cannot update appointments of a space you are not a member of"
            in update_mutation_response.errors[0].extensions["errors"]
        )

    def test_can_not_update_appointment_with_admins_permission_if_participant(self):
        create_mutation_response = create_appointment(self.user_member, self.invite_only_appointment_input_data)
        assert create_mutation_response.errors is None

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        input_data = update_input_data(
            appointment_id=appointment_id, input_data=self.another_invite_only_appointment_input_data
        )

        update_mutation_response = update_appointment(self.participant, input_data)

        assert update_mutation_response.errors is not None
        assert update_mutation_response.data is None

        assert (
            "You do not have the permission to update the appointment"
            in update_mutation_response.errors[0].extensions["errors"]
        )

    def test_can_not_update_appointment_with_participants_permission_if_not_participant(self):
        create_mutation_response = create_appointment(
            self.user_member, self.another_invite_only_appointment_input_data
        )
        assert create_mutation_response.errors is None

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        input_data = update_input_data(
            appointment_id=appointment_id, input_data=self.invite_only_appointment_input_data
        )

        update_mutation_response = update_appointment(self.another_user_member, input_data)

        assert update_mutation_response.errors is not None
        assert update_mutation_response.data is None

        assert (
            "You do not have the permission to update the appointment"
            in update_mutation_response.errors[0].extensions["errors"]
        )

    def test_can_update_public_appointment_if_admin(self):
        create_mutation_response = create_appointment(self.admin, self.public_appointment_input_data)
        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        input_data = update_input_data(
            appointment_id=appointment_id, input_data=self.invite_only_appointment_input_data
        )

        update_mutation_response = update_appointment(self.admin, input_data)

        data = update_mutation_response.data["updateAppointment"]

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

    def test_can_update_invite_only_appointment_if_admin(self):
        create_mutation_response = create_appointment(self.admin, self.invite_only_appointment_input_data)

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        input_data = update_input_data(appointment_id=appointment_id, input_data=self.public_appointment_input_data)

        update_mutation_response = update_appointment(self.admin, input_data)

        data = update_mutation_response.data["updateAppointment"]

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

    def test_can_up_invite_only_appointment_if_creator(self):
        create_mutation_response = create_appointment(self.user_member, self.invite_only_appointment_input_data)

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        input_data = update_input_data(
            appointment_id=appointment_id, input_data=self.another_invite_only_appointment_input_data
        )

        update_mutation_response = update_appointment(self.user_member, input_data)

        data = update_mutation_response.data["updateAppointment"]

        expected_start_date_time = tz.localize(
            datetime.fromisoformat(self.another_invite_only_appointment_input_data["startDateTime"])
        ).isoformat()
        expected_end_date_time = tz.localize(
            datetime.fromisoformat(self.another_invite_only_appointment_input_data["endDateTime"])
        ).isoformat()

        assert data["title"] == self.another_invite_only_appointment_input_data["title"]
        assert data["inviteOnly"]
        assert data["participants"] == [{"fullName": self.participant.profile.full_name()}]
        assert data["startDateTime"] == expected_start_date_time
        assert data["endDateTime"] == expected_end_date_time
        assert data["location"] == self.another_invite_only_appointment_input_data["location"]
        assert data["description"] == self.another_invite_only_appointment_input_data["description"]
        assert data["permission"] == self.another_invite_only_appointment_input_data["permission"]
        assert data["videoCallLink"]["url"] == self.another_invite_only_appointment_input_data["videoCallLink"]
        assert (
            data["videoCallLink"]["additionalInfo"] == self.another_invite_only_appointment_input_data["videoCallInfo"]
        )

    def test_can_update_invite_only_appointment_if_participant(self):
        create_mutation_response = create_appointment(
            self.user_member, self.another_invite_only_appointment_input_data
        )

        appointment_id = create_mutation_response.data["createAppointment"]["id"]

        input_data = update_input_data(
            appointment_id=appointment_id, input_data=self.invite_only_appointment_input_data
        )

        update_mutation_response = update_appointment(self.participant, input_data)

        data = update_mutation_response.data["updateAppointment"]

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
