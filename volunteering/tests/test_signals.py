import pytest
from unittest.mock import patch, Mock, create_autospec
import uuid

from volunteering.models import VolunteeringOpportunityStatus, Status
from volunteering.signals import publish_external_volunteering_opportunity_started


@patch("volunteering.signals.RewardsClient.submit_event")
def test_publish_external_volunteering_opportunity_started_does_not_publish_on_create(publish: Mock):
    publish_external_volunteering_opportunity_started(
        sender="volunteering.VolunteeringOpportunityStatus",
        instance=create_autospec(VolunteeringOpportunityStatus),
        created=True,
    )
    publish.assert_not_called()


@patch("volunteering.signals.RewardsClient.submit_event")
def test_publish_external_volunteering_opportunity_started_does_not_publish_without_doing_status(publish: Mock):
    volunteering_opportunity_status = create_autospec(VolunteeringOpportunityStatus)
    volunteering_opportunity_status.status = Status.CONTACTED

    publish_external_volunteering_opportunity_started(
        sender="volunteering.VolunteeringOpportunityStatus", instance=volunteering_opportunity_status, created=False
    )
    publish.assert_not_called()


@patch("volunteering.signals.RewardsClient.submit_event")
def test_publish_external_volunteering_opportunity_started_with_doing_status(publish: Mock):
    volunteering_opportunity_status = create_autospec(VolunteeringOpportunityStatus)
    volunteering_opportunity_status.status = Status.DOING
    volunteering_opportunity_status.user.username = str(uuid.uuid4())

    publish_external_volunteering_opportunity_started(
        sender="volunteering.VolunteeringOpportunityStatus", instance=volunteering_opportunity_status, created=False
    )
    publish.assert_called_once()


@patch("volunteering.signals.RewardsClient.submit_event")
def test_test_publish_external_volunteering_opportunity_started_raises_on_wrong_instance(publish: Mock):
    with pytest.raises(ValueError):
        publish_external_volunteering_opportunity_started(
            sender="volunteering.VolunteeringOpportunityStatus", instance=None, created=False
        )
    publish.assert_not_called()
