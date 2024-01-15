import uuid

from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.files.storage import default_storage
from django.contrib.gis.db import models

from imagekit.models import ProcessedImageField
from pilkit.processors import ResizeToFit

from openbook import settings
from openbook_appointments.enums import PermissionType
from openbook_appointments.helpers import upload_to_space_appointment_thumbnail_directory
from openbook_auth.models import User
from openbook_common.helpers import ExifRotate, generate_blurhash
from openbook_common.models import ModelWithUUID
from openbook_common.utils.helpers import delete_file_field
from openbook_communities.models import Community


class Appointment(ModelWithUUID):
    title = models.CharField(max_length=settings.APPOINTMENT_TITLE_MAX_LENGTH, blank=False, null=False)

    slug = models.SlugField(max_length=settings.APPOINTMENT_SLUG_MAX_LENGTH, blank=False, null=False, unique=True)

    invite_only = models.BooleanField(default=True)

    participants = models.ManyToManyField(
        User,
        related_name="appointments",
    )

    start_date_time = models.DateTimeField(blank=False)

    end_date_time = models.DateTimeField(blank=False)

    location = models.CharField(
        max_length=settings.TASK_LOCATION_MAX_LENGTH,
        blank=True,
        null=True,
        db_index=True,
    )

    geolocation = models.PointField(blank=True, null=True, spatial_index=True)

    video_call_link = models.OneToOneField(
        "VideoCallLink",
        related_name="appointment",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    description = models.TextField(
        max_length=settings.APPOINTMENT_DESCRIPTION_MAX_LENGTH,
        blank=True,
    )

    thumbnail = ProcessedImageField(
        storage=default_storage,
        verbose_name=_("thumbnail"),
        blank=True,
        null=True,
        upload_to=upload_to_space_appointment_thumbnail_directory,
        processors=[
            ExifRotate(),
            ResizeToFit(
                width=settings.CONTENT_IMAGE_MAX_DIMENSION,
                height=settings.CONTENT_IMAGE_MAX_DIMENSION,
                upscale=False,
            ),
        ],
        max_length=settings.IMAGE_URL_MAX_LENGTH,
    )

    thumbnail_blurhash = models.CharField(max_length=50, blank=True, null=True)

    permission = models.CharField(max_length=12, choices=PermissionType.choices, default=PermissionType.PARTICIPANTS)

    space = models.ForeignKey(
        Community,
        related_name="appointments",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    creator = models.ForeignKey(
        User,
        related_name="created_appointments",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    def save(self, *args, **kwargs):
        if self.thumbnail:
            self.thumbnail_blurhash = generate_blurhash(self.thumbnail)

        if not self.slug:
            base_slug = slugify(self.title)
            suffix = str(uuid.uuid4())[:8]
            self.slug = f"{base_slug}-{suffix}"

        super().save(*args, **kwargs)

    def delete_thumbnail(self):
        if self.thumbnail:
            delete_file_field(self.thumbnail)
            self.thumbnail_blurhash = None
            self.thumbnail = None
            self.thumbnail.delete()

    def update_thumbnail(self, thumbnail):
        if self.thumbnail:
            self.delete_thumbnail()

        self.thumbnail = thumbnail

        return self.thumbnail


class VideoCallLink(ModelWithUUID):
    url = models.URLField(blank=False, max_length=settings.VIDEO_CALL_LINK_URL_MAX_LENGTH)

    additional_info = models.TextField(
        max_length=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH, blank=True, null=True
    )
