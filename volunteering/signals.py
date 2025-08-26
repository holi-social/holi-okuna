from functools import partial
from typing import TYPE_CHECKING
from openbook_common.pubsub.event import Event
from openbook_common.pubsub.publisher import publish_event
from openbook_common.pubsub.topic import Topic
from openbook_common.utils.model_loaders import get_volunteering_opportunity_status_model

if TYPE_CHECKING:
    from volunteering.models import VolunteeringOpportunityStatus

publish_to_okuna_topic = partial(publish_event, Topic.OKUNA.value)


class ExternalVolunteeringOpportunityStartedEvent(Event):
    def __init__(self, volunteering_opportunity_status: "VolunteeringOpportunityStatus"):
        self.volunteering_opportunity_status = volunteering_opportunity_status

        super().__init__(
            data={},
            event_type="ExternalVolunteeringOpportunityStarted",
            event_version="1.0.0",
            additional_attributes={
                "userId": self.volunteering_opportunity_status.user.username,
            },
        )

    def log_str(self) -> str:
        return f"ExternalVolunteeringOpportunityStarted(external_volunteering_opportunity_id={self.volunteering_opportunity_status.external_volunteering_opportunity_id})"


def publish_external_volunteering_opportunity_started(instance, created: bool, **kwargs):
    from volunteering.models import Status

    volunteering_opportunity_status = get_volunteering_opportunity_status_model()

    if created:
        return

    if not isinstance(instance, volunteering_opportunity_status):
        raise ValueError("wrong model connected to signal handler")

    if instance.status == Status.DOING:
        publish_to_okuna_topic(ExternalVolunteeringOpportunityStartedEvent(volunteering_opportunity_status=instance))
