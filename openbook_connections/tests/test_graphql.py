import logging

import pytest
from django.test import AsyncClient

from openbook_auth.models import UserConnectionStatus
from openbook_common.tests.helpers import (
    make_user,
)
from django.core.management import call_command
from openbook_connections.tests.helpers import connect_to_user

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestConnections:
    def test_can_perform_connection_workflow(self):
        first_user = make_user(name="Fritz", last_name="Meier")
        second_user = make_user(name="Gesine", last_name="Schinder")

        assert first_user.is_connected_with_user(second_user) is False

        connection_request_response = connect_to_user(first_user, second_user)

        assert connection_request_response.data["updateConnectionWithUser"]["id"] == second_user.username

        assert second_user.is_pending_confirm_connection_for_user_with_id(first_user.pk) is True
        assert first_user.get_connection_status_with_user_id(second_user.pk) == UserConnectionStatus.REQUESTED

        connection_confirm_response = connect_to_user(second_user, first_user)

        assert connection_confirm_response.data["updateConnectionWithUser"]["id"] == first_user.username

        assert first_user.is_fully_connected_with_user_with_id(second_user.pk) is True
        assert second_user.is_fully_connected_with_user_with_id(first_user.pk) is True
