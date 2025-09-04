from django.apps import AppConfig
from django.db.models.signals import post_save

from openbook_communities.signals import publish_task_completed


class OpenbookCommunitiesConfig(AppConfig):
    name = "openbook_communities"

    def ready(self):
        # Use lazy signal connection to avoid import issues
        from openbook_communities.models.completed_task import CompletedTask

        post_save.connect(
            publish_task_completed,
            sender=CompletedTask,
            dispatch_uid="publish_task_completed",
        )
