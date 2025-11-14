import pytest
from unittest.mock import patch, Mock, create_autospec
import uuid

from petitions.models import PetitionStatus, Status
from petitions.signals import publish_external_petition_signed


@patch("petitions.signals.RewardsClient.submit_event")
def test_publish_external_petition_signed_does_not_publish_on_create(publish: Mock):
    publish_external_petition_signed(
        sender="petitions.PetitionStatus",
        instance=create_autospec(PetitionStatus),
        created=True,
    )
    publish.assert_not_called()


@patch("petitions.signals.RewardsClient.submit_event")
def test_publish_external_petition_signed_does_not_publish_without_signed_status(publish: Mock):
    petition_status = create_autospec(PetitionStatus)
    petition_status.status = Status.PLANNED

    publish_external_petition_signed(sender="petitions.PetitionStatus", instance=petition_status, created=False)
    publish.assert_not_called()


@patch("petitions.signals.RewardsClient.submit_event")
def test_publish_external_petition_signed_with_signed_status(publish: Mock):
    petition_status = create_autospec(PetitionStatus)
    petition_status.status = Status.SIGNED
    petition_status.user.username = str(uuid.uuid4())

    publish_external_petition_signed(sender="petitions.PetitionStatus", instance=petition_status, created=False)
    publish.assert_called_once()


@patch("petitions.signals.RewardsClient.submit_event")
def test_publish_external_petition_signed_raises_on_wrong_instance(publish: Mock):
    with pytest.raises(ValueError):
        publish_external_petition_signed(sender="petitions.PetitionStatus", instance=None, created=False)
    publish.assert_not_called()
