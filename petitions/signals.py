from typing import TYPE_CHECKING
from uuid import UUID

from openbook_common.rewards_api import RewardsClient, Event
from openbook_common.rewards_api.event import EmptyPayload
from openbook_common.utils.model_loaders import get_petition_status_model

if TYPE_CHECKING:
    from petitions.models import PetitionStatus


ExternalPetitionSignedEvent = Event[EmptyPayload]


def publish_external_petition_signed(instance: "PetitionStatus", created: bool, **kwargs):
    from petitions.models import Status

    petition_status = get_petition_status_model()

    if created:
        return

    if not isinstance(instance, petition_status):
        raise ValueError("wrong model connected to signal handler")

    if instance.status != Status.SIGNED:
        return

    event = ExternalPetitionSignedEvent(
        user_id=UUID(instance.user.username),
        event_type="ExternalPetitionSigned",
        data=EmptyPayload(),
    )

    RewardsClient.submit_event(event)
