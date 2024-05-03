import uuid

from django.contrib.gis.db import models
from django.core.files.storage import default_storage
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from imagekit.models import ProcessedImageField
from pilkit.processors import ResizeToFit

from openbook import settings
from openbook_auth.models import User
from openbook_common.helpers import ExifRotate, generate_blurhash
from openbook_common.models import ModelWithUUID
from openbook_common.utils.helpers import delete_file_field
from openbook_terms.models import Topic, FeedPostCategory
from feed_posts.enums import VisibilityLevel
from feed_posts.helpers import upload_to_feed_post_images_directory


class FeedPost(ModelWithUUID):
    title = models.CharField(max_length=settings.FEED_POST_TITLE_MAX_LENGTH, blank=True, null=True)

    slug = models.SlugField(max_length=settings.FEED_POST_SLUG_MAX_LENGTH, blank=False, null=False, unique=True)

    description = models.TextField(max_length=settings.FEED_POST_DESCRIPTION_MAX_LENGTH, blank=False, null=False)

    visibility = models.CharField(max_length=21, choices=VisibilityLevel.choices, default=VisibilityLevel.PUBLIC)

    topics = models.ManyToManyField(Topic, related_name="feed_posts", blank=True, db_index=True)

    category = models.ForeignKey(FeedPostCategory, on_delete=models.SET_NULL, null=True)

    creator = models.ForeignKey(
        User,
        related_name="created_feed_posts",
        on_delete=models.SET_NULL,
        null=True,
    )

    created_at = models.DateTimeField(editable=False, auto_now_add=True)

    image = ProcessedImageField(
        storage=default_storage,
        verbose_name=_("thumbnail"),
        blank=True,
        null=True,
        upload_to=upload_to_feed_post_images_directory,
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

    image_blurhash = models.CharField(max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.image:
            self.image_blurhash = generate_blurhash(self.image)

        if not self.slug:
            base_slug = slugify(self.title)
            suffix = str(uuid.uuid4())[:8]
            self.slug = f"{base_slug}-{suffix}"

        super().save(*args, **kwargs)

    def delete_image(self):
        if self.image:
            delete_file_field(self.image)
            self.image_blurhash = None
            self.image = None
            self.image.delete()

    def update_image(self, image):
        if self.image:
            self.delete_image()

        self.image = image
