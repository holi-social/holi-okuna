from functools import partial
from typing import TYPE_CHECKING
from openbook_common.pubsub.event import Event
from openbook_common.pubsub.publisher import publish_event
from openbook_common.pubsub.topic import Topic

if TYPE_CHECKING:
    from openbook_communities.models.completed_task import CompletedTask

publish_to_okuna_topic = partial(publish_event, Topic.OKUNA.value)


class TaskCompletedEvent(Event):
    def __init__(self, completed_task: "CompletedTask"):
        self.completed_task = completed_task

        super().__init__(
            data={},
            event_type="TaskCompleted",
            event_version="1.0.0",
            additional_attributes={
                "userId": self.completed_task.user.username,
                "taskId": self.completed_task.task.id,
                "taskType": self.completed_task.task.interaction_type,
            },
        )

    def log_str(self) -> str:
        return f"TaskCompleted(completed_task_id={self.completed_task.id})"


def publish_task_completed(instance, created: bool, **kwargs):
    if not created:
        return

    publish_to_okuna_topic(TaskCompletedEvent(completed_task=instance))
