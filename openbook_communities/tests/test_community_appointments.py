from unittest import mock
from unittest.mock import patch

import pytest
import logging
from django.test import AsyncClient, TestCase
from django.utils import timezone
import datetime

from django.contrib.auth.models import AnonymousUser

from openbook_appointments.services import AppointmentService
from openbook_common.tests.helpers import make_user, make_community
from openbook_communities.tests.helpers import get_space_by_id_with_appointments
from openbook_notifications.notifications import Notification

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.mark.django_db
class TestSpaceAppointments(TestCase):
    mock_current_datetime = timezone.datetime(2024, 6, 14, 12, 0, 0)

    # prevent sending novu notifications
    @pytest.fixture(scope="class", autouse=True)
    def setup(self):
        with mock.patch.object(Notification, "send"):
            yield

    @classmethod
    def setUpTestData(cls):
        cls.anonymous_user = AnonymousUser()
        cls.admin_user = make_user()
        cls.member_user = make_user()
        cls.external_user = make_user()
        cls.space = make_community(creator=cls.admin_user)

        cls.space.add_member(cls.member_user)
        cls.location_details = {
            "completeAddress": "Munich, Bavaria, Germany",
            "city": "Munich",
            "state": "Bavaria",
            "country": "Germany",
            "geolocation": {
                "latitude": 48.1371079,
                "longitude": 11.5753822,
            },
        }

        cls.old_public_appointment = AppointmentService().create_appointment(
            space_id=cls.space.id,
            title="Public Appointment",
            invite_only=False,
            participant_ids=[],
            start_date_time=timezone.make_aware(datetime.datetime(2023, 1, 15, 12)),
            end_date_time=timezone.make_aware(datetime.datetime(2023, 1, 15, 13)),
            location_details=cls.location_details,
            description="This is an old public appointment",
            permission="ADMINS",
            creator=cls.admin_user,
            video_call_link="https://zoom.us/j/1234666789",
        )

        cls.hybrid_public_appointment = AppointmentService().create_appointment(
            space_id=cls.space.id,
            title="Public Appointment",
            invite_only=False,
            participant_ids=[],
            start_date_time=timezone.make_aware(datetime.datetime(2024, 6, 16, 8)),
            end_date_time=timezone.make_aware(datetime.datetime(2024, 6, 16, 10)),
            location_details=cls.location_details,
            description="This is a public appointment where everybody is welcome",
            permission="ADMINS",
            creator=cls.admin_user,
            video_call_link="https://zoom.us/j/123456789",
        )

        cls.digital_public_appointment = AppointmentService().create_appointment(
            space_id=cls.space.id,
            title="Digital Public Appointment",
            invite_only=False,
            participant_ids=[],
            start_date_time=timezone.make_aware(datetime.datetime(2024, 6, 16, 11)),
            end_date_time=timezone.make_aware(datetime.datetime(2024, 6, 16, 12)),
            description="This is a public appointment where everybody is welcome",
            permission="ADMINS",
            creator=cls.admin_user,
            video_call_link="https://zoom.us/j/123456789",
        )

        cls.on_site_public_appointment = AppointmentService().create_appointment(
            space_id=cls.space.id,
            title="On-site Public Appointment",
            invite_only=False,
            participant_ids=[],
            start_date_time=timezone.make_aware(datetime.datetime(2024, 6, 17, 8)),
            end_date_time=timezone.make_aware(datetime.datetime(2024, 6, 17, 10)),
            location_details=cls.location_details,
            description="This is a another public appointment where everybody is welcome",
            permission="ADMINS",
            creator=cls.admin_user,
        )

        cls.invite_only_appointment = AppointmentService().create_appointment(
            space_id=cls.space.id,
            title="Public Appointment",
            invite_only=True,
            participant_ids=[],
            start_date_time=timezone.make_aware(datetime.datetime(2024, 6, 18, 8)),
            end_date_time=timezone.make_aware(datetime.datetime(2024, 6, 18, 10)),
            location_details=cls.location_details,
            description="This is a invite_only appointment where only invited people are welcome",
            permission="PARTICIPANTS",
            creator=cls.admin_user,
            video_call_link="https://zoom.us/j/123456789",
        )

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_can_only_retrieve_upcoming_appointments(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.member_user)
        assert response["appointments"]["totalResults"] == 4
        assert str(self.old_public_appointment.id) not in [
            appointment["id"] for appointment in response["appointments"]["data"]
        ]

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_upcoming_appointments_ordered_chronologically(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.member_user)
        assert response["appointments"]["totalResults"] == 4
        assert response["appointments"]["data"][0]["id"] == str(self.hybrid_public_appointment.id)
        assert response["appointments"]["data"][1]["id"] == str(self.digital_public_appointment.id)
        assert response["appointments"]["data"][2]["id"] == str(self.on_site_public_appointment.id)
        assert response["appointments"]["data"][3]["id"] == str(self.invite_only_appointment.id)

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_all_users_can_retrieve_all_public_appointments(self, mock_current_datetime):
        # space member
        response = get_space_by_id_with_appointments(self.space.id, self.member_user)
        assert response["appointments"]["totalResults"] == 4  # 3 public + 1 invite_only

        # external user
        response = get_space_by_id_with_appointments(self.space.id, self.external_user)
        assert response["appointments"]["totalResults"] == 3

        # anonymous user
        response = get_space_by_id_with_appointments(self.space.id, AnonymousUser)
        assert response["appointments"]["totalResults"] == 3

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_member_users_can_retrieve_all_appointments_details(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.member_user)
        assert response["appointments"]["totalResults"] == 4
        assert (
            response["appointments"]["data"][0]["locationDetails"]["completeAddress"]
            == self.hybrid_public_appointment.location_details.complete_address
        )
        assert (
            response["appointments"]["data"][0]["videoCallLink"]["url"]
            == self.hybrid_public_appointment.video_call_link.url
        )
        assert response["appointments"]["data"][0]["isHybrid"] is True
        assert response["appointments"]["data"][0]["hasVideoCallLink"] is True

        assert response["appointments"]["data"][1]["locationDetails"] is None

        assert (
            response["appointments"]["data"][1]["videoCallLink"]["url"]
            == self.digital_public_appointment.video_call_link.url
        )
        assert response["appointments"]["data"][1]["isHybrid"] is False
        assert response["appointments"]["data"][1]["hasVideoCallLink"] is True

        assert (
            response["appointments"]["data"][2]["locationDetails"]["completeAddress"]
            == self.on_site_public_appointment.location_details.complete_address
        )
        assert response["appointments"]["data"][2]["videoCallLink"] is None
        assert response["appointments"]["data"][2]["isHybrid"] is False
        assert response["appointments"]["data"][2]["hasVideoCallLink"] is False

        assert (
            response["appointments"]["data"][3]["locationDetails"]["completeAddress"]
            == self.invite_only_appointment.location_details.complete_address
        )
        assert (
            response["appointments"]["data"][3]["videoCallLink"]["url"]
            == self.invite_only_appointment.video_call_link.url
        )
        assert response["appointments"]["data"][3]["isHybrid"] is True
        assert response["appointments"]["data"][3]["hasVideoCallLink"] is True

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_external_users_can_not_retrieve_invite_only_appointments(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.external_user)
        assert response["appointments"]["totalResults"] == 3
        assert str(self.invite_only_appointment.id) not in [
            appointment["id"] for appointment in response["appointments"]["data"]
        ]

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_external_users_can_retrieve_public_appointments_details(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.external_user)
        assert response["appointments"]["totalResults"] == 3

        # Hybrid public appointment
        assert (
            response["appointments"]["data"][0]["locationDetails"]["completeAddress"]
            == self.hybrid_public_appointment.location_details.complete_address
        )
        assert (
            response["appointments"]["data"][0]["videoCallLink"]["url"]
            == self.hybrid_public_appointment.video_call_link.url
        )
        assert response["appointments"]["data"][0]["isHybrid"] is True
        assert response["appointments"]["data"][0]["hasVideoCallLink"] is True

        # Digital public appointment
        assert response["appointments"]["data"][1]["locationDetails"] is None
        assert (
            response["appointments"]["data"][1]["videoCallLink"]["url"]
            == self.digital_public_appointment.video_call_link.url
        )
        assert response["appointments"]["data"][1]["isHybrid"] is False
        assert response["appointments"]["data"][1]["hasVideoCallLink"] is True

        # On-site public appointment
        assert (
            response["appointments"]["data"][2]["locationDetails"]["completeAddress"]
            == self.on_site_public_appointment.location_details.complete_address
        )
        assert response["appointments"]["data"][2]["videoCallLink"] is None
        assert response["appointments"]["data"][2]["isHybrid"] is False
        assert response["appointments"]["data"][2]["hasVideoCallLink"] is False

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_anonymous_users_can_not_retrieve_invite_only_appointments(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.external_user)
        assert response["appointments"]["totalResults"] == 3
        assert str(self.invite_only_appointment.id) not in [
            appointment["id"] for appointment in response["appointments"]["data"]
        ]

    @patch("django.utils.timezone.now", return_value=mock_current_datetime)
    def test_anonymous_users_can_not_retrieve_public_appointments_details(self, mock_current_datetime):
        response = get_space_by_id_with_appointments(self.space.id, self.anonymous_user)

        # Hybrid public appointment
        assert response["appointments"]["totalResults"] == 3
        assert (
            not response["appointments"]["data"][0]["locationDetails"]["completeAddress"]
            == self.hybrid_public_appointment.location_details.complete_address
        )
        assert (
            response["appointments"]["data"][0]["locationDetails"]["completeAddress"]
            == f"{self.hybrid_public_appointment.location_details.city}, {self.hybrid_public_appointment.location_details.country}"
        )
        assert response["appointments"]["data"][0]["locationDetails"]["geolocation"] is None
        assert response["appointments"]["data"][0]["videoCallLink"] is None

        # Digital public appointment
        assert response["appointments"]["data"][1]["locationDetails"] is None
        assert response["appointments"]["data"][1]["videoCallLink"] is None
        assert response["appointments"]["data"][1]["isHybrid"] is False
        assert response["appointments"]["data"][1]["hasVideoCallLink"] is True

        # On-site public appointment
        assert (
            not response["appointments"]["data"][2]["locationDetails"]["completeAddress"]
            == self.on_site_public_appointment.location_details.complete_address
        )
        assert (
            response["appointments"]["data"][2]["locationDetails"]["completeAddress"]
            == f"{self.on_site_public_appointment.location_details.city}, {self.on_site_public_appointment.location_details.country}"
        )
        assert response["appointments"]["data"][2]["videoCallLink"] is None
        assert response["appointments"]["data"][2]["isHybrid"] is False
        assert response["appointments"]["data"][2]["hasVideoCallLink"] is False
