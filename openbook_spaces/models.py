from django.db import models
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from imagekit.models import ProcessedImageField
from pilkit.processors import ResizeToFit

# Create your models here.
from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_spaces.helpers import upload_to_spaces_main_image_directory
from openbook_terms.models import Topic

# TODO Think about what to do for storage backend

space_image_storage = default_storage


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
    main_image = ProcessedImageField(
        verbose_name=_("main_image"),
        storage=space_image_storage,
        blank=False,
        null=True,
        format="JPEG",
        options={"quality": 90},
        processors=[
            ResizeToFit(width=settings.SPACE_IMAGE_RESIZE_WIDTH, upscale=False)
        ],
        upload_to=upload_to_spaces_main_image_directory,
        max_length=settings.IMAGE_URL_MAX_LENGTH,
    )
    location = models.CharField(
        max_length=settings.SPACE_LOCATION_MAX_LENGTH, blank=True, null=True
    )
    topics = models.ManyToManyField(Topic, related_name="spaces")

    def __str__(self):
        return f"{self.__class__.__name__}: {self.title} ({self.id})"


class SpaceMember(ModelWithUUID):
    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="spaces_memberships",
        null=True,
        blank=True,
    )
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, related_name="members", null=True, blank=True
    )

    class Meta:
        unique_together = (
            "space",
            "member",
        )
        indexes = [
            models.Index(fields=["space", "member"]),
        ]


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
