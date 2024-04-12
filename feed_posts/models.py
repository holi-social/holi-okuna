import uuid

from django.contrib.gis.db import models
from django.utils.text import slugify

from feed_posts.enums import VisibilityLevel
from openbook import settings
from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_terms.models import Topic, FeedPostCategory


class FeedPost(ModelWithUUID):
    title = models.CharField(max_length=settings.FEED_POST_TITLE_MAX_LENGTH, blank=False, null=False)

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

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            suffix = str(uuid.uuid4())[:8]
            self.slug = f"{base_slug}-{suffix}"

        super().save(*args, **kwargs)
