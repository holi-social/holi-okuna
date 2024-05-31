from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.utils.translation import gettext_lazy as _
from imagekit.models import ProcessedImageField
from pilkit.processors import ResizeToFit

from openbook_auth.models import User
from openbook_common.helpers import ExifRotate, generate_blurhash
from openbook_common.models import ModelWithUUID
from openbook_insights.helpers import upload_to_insight_directory
from openbook_posts.models import Post
from openbook_terms.models import Topic
from openbook_polls.models import Poll

insight_image_storage = default_storage


class Insight(ModelWithUUID):
    title = models.CharField(max_length=settings.INSIGHT_TITLE_MAX_LENGTH, blank=False)
    description = models.TextField(blank=False)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="curated_insights",
        blank=False,
        null=True,
    )
    date_published = models.DateField(blank=False)
    header_image = ProcessedImageField(
        verbose_name=_("header image"),
        storage=insight_image_storage,
        upload_to=upload_to_insight_directory,
        blank=False,
        null=True,
        # constrain to maximum width
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
    header_image_blurhash = models.CharField(max_length=50, blank=True, null=True)
    # todo gregor: remove this as soon as we don't show legacy Post-based Insights in the app anymore
    posts = models.ManyToManyField(Post, related_name="insights", blank=True)
    polls = models.ManyToManyField(Poll, related_name="insights", null=True, blank=True)
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        related_name="insights",
        blank=True,
        null=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["-date_published"]),
        ]

    def save(self, *args, **kwargs):
        if self.header_image:
            self.header_image_blurhash = generate_blurhash(self.header_image)
        super().save(*args, **kwargs)
