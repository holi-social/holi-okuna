from typing import TYPE_CHECKING
from uuid import UUID

from openbook_common.rewards_api import RewardsClient, Event
from openbook_common.rewards_api.event import EmptyPayload
from openbook_common.utils.model_loaders import get_volunteering_opportunity_status_model

if TYPE_CHECKING:
    from volunteering.models import VolunteeringOpportunityStatus


ExternalVolunteeringOpportunityStartedEvent = Event[EmptyPayload]


def publish_external_volunteering_opportunity_started(
    instance: "VolunteeringOpportunityStatus", created: bool, **kwargs
):
    from volunteering.models import Status

    volunteering_opportunity_status = get_volunteering_opportunity_status_model()

    if created:
        return

    if not isinstance(instance, volunteering_opportunity_status):
        raise ValueError("wrong model connected to signal handler")

    if instance.status != Status.DOING:
        return

    event = ExternalVolunteeringOpportunityStartedEvent(
        user_id=UUID(instance.user.username),
        event_type="ExternalVolunteeringOpportunityStarted",
        data=EmptyPayload(),
    )

    RewardsClient.submit_event(event)
