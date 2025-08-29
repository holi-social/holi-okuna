from django.contrib.gis.db import models

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_communities.models import Task


class CompletedTask(ModelWithUUID):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="completions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="completed_tasks")
    completed_at = models.DateTimeField(auto_now_add=True)
