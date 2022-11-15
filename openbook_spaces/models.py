from django.db import models
from django.conf import settings
from django.utils.timezone import now
from django.db.models import JSONField
from django.utils.translation import gettext_lazy as _

# Create your models here.
from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_terms.models import Skill


class Space(ModelWithUUID):
    title = models.CharField(max_length=settings.SPACE_TITLE_MAX_LENGTH, blank=False)
    description = models.TextField(blank=False)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_spaces",
        blank=True,
        null=True,
    )
    created = models.DateTimeField(default=now, editable=False)


class Task(ModelWithUUID):
    class Regularity(models.TextChoices):
        REGULARLY = "regularly", _("regularly")
        PROJECT_BASED = "project-based", _("project-based")
        ONE_TIME = "one-time", _("one-time")

    name = models.CharField(max_length=settings.TASK_NAME_MAX_LENGTH, blank=False)
    description = models.TextField(blank=False)
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, related_name="tasks", blank=False, null=False
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
