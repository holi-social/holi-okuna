import uuid

from django.conf import settings
from django.db import models
from django.core.files.storage import default_storage
from django.utils.translation import gettext_lazy as _

from imagekit.models import ProcessedImageField
from pilkit.processors import ResizeToFit

# Create your models here.
from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_insights.helpers import upload_to_insight_directory
from openbook_posts.models import Post
from openbook_terms.models import Topic

# TODO Think about what to do for storage backend
# insight_image_storage = S3PrivateMediaStorage() if settings.IS_PRODUCTION else default_storage
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
        verbose_name=_("header_image"),
        storage=insight_image_storage,
        upload_to=upload_to_insight_directory,
        blank=False,
        null=True,
        format="JPEG",
        options={"quality": 80},
        # constrain to maximum width
        processors=[ResizeToFit(width=1024, upscale=False)],
        max_length=settings.IMAGE_URL_MAX_LENGTH,
    )
    posts = models.ManyToManyField(Post, related_name="insights")
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        related_name="insights",
        blank=True,
        null=True,
    )
