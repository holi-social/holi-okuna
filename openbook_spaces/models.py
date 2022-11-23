from django.db import models
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_communities.models import Community
from openbook_terms.models import Skill


class Task(ModelWithUUID):
    class Regularity(models.TextChoices):
        REGULARLY = "regularly", _("regularly")
        PROJECT_BASED = "project-based", _("project-based")
        ONE_TIME = "one-time", _("one-time")

    name = models.CharField(max_length=settings.TASK_NAME_MAX_LENGTH, blank=False)
    description = models.TextField(blank=False)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="tasks",
        blank=False,
        null=False,
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_tasks",
        blank=True,
        null=True,
    )
    created = models.DateTimeField(default=now, editable=False)
    slots_available = models.PositiveIntegerField(blank=False)
    slots_taken = models.PositiveIntegerField(blank=False)
    location = models.CharField(
        max_length=settings.TASK_LOCATION_MAX_LENGTH, blank=False
    )
    regularity = models.CharField(
        max_length=13,
        choices=Regularity.choices,
    )
    skills = models.ManyToManyField(Skill, related_name="tasks", blank=True)
