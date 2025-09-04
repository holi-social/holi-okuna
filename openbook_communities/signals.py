from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from openbook_common.rewards_api import RewardsClient, Event

if TYPE_CHECKING:
    from openbook_communities.models.completed_task import CompletedTask


@dataclass(frozen=True)
class TaskCompletedPayload:
    category: str

    def as_dict(self) -> dict:
        return {
            "category": self.category,
        }


class TaskCompletedEvent(Event[TaskCompletedPayload]):
    pass


def publish_task_completed(instance: "CompletedTask", created: bool, **kwargs):
    if not created:
        return

    event = TaskCompletedEvent(
        user_id=UUID(instance.user.username),
        event_type="TaskCompleted",
        data=TaskCompletedPayload(category=instance.task.interaction_type),
    )

    RewardsClient.submit_event(event)
