import uuid
from datetime import timedelta
from typing import Optional

from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from imagekit.models import ProcessedImageField
from pilkit.processors import ResizeToFit
from rest_framework.exceptions import ValidationError

from comments.models import Comment
from comments.models.commentable_notification_context import CommentNotificationMixin, CommentNotificationContext
from feed_posts.enums import VisibilityLevel, AspectRatio
from feed_posts.helpers import upload_to_feed_post_images_directory, upload_to_new_feed_post_images_directory
from openbook import settings
from openbook_auth.models import User, UserRole
from openbook_common.enums import ReactionType
from openbook_common.helpers import ExifRotate, generate_blurhash, geojson_from_geolocation
from openbook_common.models import ModelWithUUID, LinkPreview
from openbook_common.types import LanguageCode
from openbook_common.utils.helpers import delete_file_field
from openbook_polls.models import Poll
from openbook_terms.models import Topic, FeedPostCategory


class FeedPost(CommentNotificationMixin, ModelWithUUID):
    title = models.CharField(max_length=settings.FEED_POST_TITLE_MAX_LENGTH, blank=True, null=True)

    slug = models.SlugField(max_length=settings.FEED_POST_SLUG_MAX_LENGTH, blank=False, null=False, unique=True)

    description = models.TextField(max_length=settings.FEED_POST_DESCRIPTION_MAX_LENGTH, blank=False, null=False)

    visibility = models.CharField(max_length=21, choices=VisibilityLevel.choices, default=VisibilityLevel.PUBLIC)

    topics = models.ManyToManyField(Topic, related_name="feed_posts", blank=True, db_index=True)

    topics_v2 = ArrayField(models.CharField(max_length=settings.TERM_SLUG_MAX_LENGTH), blank=True, default=list)

    category = models.ForeignKey(FeedPostCategory, on_delete=models.PROTECT, null=True)

    poll = models.ForeignKey(Poll, on_delete=models.PROTECT, null=True)

    creator = models.ForeignKey(
        User,
        related_name="created_feed_posts",
        on_delete=models.CASCADE,
        null=True,
    )

    created_at = models.DateTimeField(editable=False, auto_now_add=True)
    # This field is deprecated. Please use the new FeedPostImage model instead. Remove it after version 1.30.x
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
    # This field is deprecated. Please use the new FeedPostImage model instead. Remove it after version 1.30.x
    image_blurhash = models.CharField(max_length=50, blank=True, null=True)

    link_preview = models.ForeignKey(LinkPreview, null=True, blank=True, on_delete=models.SET_NULL)

    language_code = models.CharField(
        max_length=2, choices=LanguageCode.choices, blank=True, null=True, verbose_name=_("language")
    )

    location = models.CharField(
        max_length=settings.COMPLETE_ADDRESS_MAX_LENGTH,
        blank=True,
        null=True,
        db_index=True,
    )

    geolocation = models.PointField(blank=True, null=True, spatial_index=True)
    # also store as GeoJSON as downstream processes (Google Datastream) can't understand Postgis binary format
    geolocation_geojson = models.JSONField(blank=True, null=True)

    priority_duration = models.PositiveIntegerField(
        default=0,
        help_text="Specifies how many days the post will remain at the top of the feed.",
    )

    image_urls = ArrayField(
        models.URLField(max_length=settings.IMAGE_URL_MAX_LENGTH), blank=True, null=True, default=list
    )

    aspect_ratio = models.CharField(max_length=20, choices=AspectRatio.choices, blank=True, null=True)

    class Meta:
        indexes = [GinIndex(fields=["topics_v2"])]

    @property
    def has_priority(self):
        if (
            self.creator.role == UserRole.CO_FOUNDER
            and self.category is not None
            and self.category.slug == "founder-update"
        ):
            return self.created_at + timedelta(days=self.priority_duration) >= timezone.now()
        return False

    def save(self, *args, **kwargs):
        if self.image and not self.image_blurhash:
            self.image_blurhash = generate_blurhash(self.image)
        if not self.slug:
            base_slug = slugify(self.title)
            suffix = str(uuid.uuid4())[:8]
            self.slug = f"{base_slug}-{suffix}"
        if self.geolocation:
            self.geolocation_geojson = geojson_from_geolocation(self.geolocation)
        else:
            self.geolocation_geojson = None

        super().save(*args, **kwargs)

    def comment_on(self, commenter: User, text: str, language: Optional[str]):
        return Comment.create_comment(text=text, commenter=commenter, commentable=self, language=language)

    def delete_comment(self, commenter: User, id: uuid.UUID):
        comment = Comment.objects.get(pk=id)
        is_comment_creator = comment.commenter_id == commenter.id

        if is_comment_creator:
            comment.delete()
        else:
            raise ValidationError(_("You cannot remove a comment that does not belong to you"))

    def can_be_viewed(self, user: User) -> bool:
        return True

    @property
    def comment_notification_context(self) -> CommentNotificationContext:
        return CommentNotificationContext(id=self.id, title=self.title, context=None)


class FeedPostReaction(ModelWithUUID):
    feed_post = models.ForeignKey(FeedPost, on_delete=models.CASCADE, related_name="reactions")
    reactor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feed_post_reactions")
    reaction_type = models.CharField(max_length=20, choices=ReactionType.choices)
    created_at = models.DateTimeField(editable=False, auto_now_add=True)

    class Meta:
        unique_together = (
            "reactor",
            "feed_post",
        )


class FeedPostMention(ModelWithUUID):
    feed_post = models.ForeignKey(FeedPost, on_delete=models.CASCADE, related_name="mentions")
    mention = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feed_post_mentions")
    created_at = models.DateTimeField(editable=False, auto_now_add=True)

    class Meta:
        unique_together = (
            "feed_post",
            "mention",
        )


class FeedPostImage(ModelWithUUID):
    feed_post = models.ForeignKey(FeedPost, on_delete=models.CASCADE, related_name="images")
    image = ProcessedImageField(
        storage=default_storage,
        verbose_name=_("image"),
        upload_to=upload_to_new_feed_post_images_directory,
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
    order = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(editable=False, auto_now_add=True)
    alt_text = models.TextField(max_length=settings.CONTENT_IMAGE_ALT_TEXT_MAX_LENGTH, blank=True, null=True)
    aspect_ratio = models.CharField(max_length=20, choices=AspectRatio.choices, blank=True, null=True)

    class Meta:
        ordering = ["order"]
        unique_together = (
            "feed_post",
            "image",
            "order",
        )

    def save(self, *args, **kwargs):
        self.image_blurhash = generate_blurhash(self.image)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        delete_file_field(self.image)


class FeedConfig(models.Model):
    priority_duration = models.PositiveIntegerField(
        default=7, help_text="Specifies how many days the posts will be prioritized."
    )

    class Meta:
        verbose_name = "Feed Configuration"
        verbose_name_plural = "Feed Configurations"

    def save(self, *args, **kwargs):
        if not self.pk and FeedConfig.objects.exists():
            raise ValueError("Only one feed configuration allowed")
        super().save(*args, **kwargs)
