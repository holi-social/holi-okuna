import unittest
import uuid
from unittest.mock import Mock, patch

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Manager as ModelManager, Q

from openbook_appointments.enums import StatusType
from openbook_appointments.models import Appointment
from openbook_appointments.repositories import AppointmentRepository


class AppointmentRepositoryTestCase(unittest.TestCase):
    appointment_models: Mock | ModelManager
    repo: AppointmentRepository

    def setUp(self):
        self.appointment_models = Mock(spec=ModelManager)

        appointment_mock = Mock(spec=Appointment)
        appointment_mock.objects = self.appointment_models

        self.appointment_patcher = patch("openbook_appointments.repositories.Appointment", new=appointment_mock)
        self.appointment_patcher.start()

        self.repo = AppointmentRepository()

    def tearDown(self) -> None:
        self.appointment_patcher.stop()

    def test_it_does_not_fetch_deleted_appointments_by_default(self) -> None:
        """Test that without explicit opt-in, the repository never returns deleted appointments."""
        self.repo.get_appointments(space_id=uuid.uuid4(), status_type=StatusType.UPCOMING)
        self.appointment_models.filter.assert_called_once()
        filter_query: Q = self.appointment_models.filter.call_args.args[0]

        assert ("is_deleted", False) in filter_query

    def test_it_fetches_deleted_appointments_when_requested(self) -> None:
        """When we explicitly opt in, we should not filter out deleted appointments."""
        self.repo.get_appointments(space_id=uuid.uuid4(), status_type=StatusType.UPCOMING, include_deleted=True)
        self.appointment_models.filter.assert_called_once()
        filter_query: Q = self.appointment_models.filter.call_args.args[0]

        assert "is_deleted" not in [fq[0] for fq in filter_query.children]

    def test_it_raises_exception_when_trying_to_access_a_deleted_appointment(self) -> None:
        """
        When fetching a single appointment, it should not return the appointment if it's deleted.
        Instead, it should behave as if no result was found.
        """
        deleted_appointment: Appointment = Appointment(
            title="test appt",
            slug="test-1",
            is_deleted=True,
        )
        self.appointment_models.filter.get.return_value = deleted_appointment

        with self.assertRaises(ObjectDoesNotExist):
            self.repo.get_appointment(id_or_slug="test-1", allow_deleted=False)

    def test_it_gets_deleted_appointment_if_requested(self) -> None:
        """When we explicitly opt in, we should be able to fetch a deleted appointment."""
        deleted_appointment: Appointment = Appointment(
            title="test appt",
            slug="test-1",
            is_deleted=True,
        )
        self.appointment_models.filter.get.return_value = deleted_appointment

        assert self.repo.get_appointment(id_or_slug="test-1", allow_deleted=True)
