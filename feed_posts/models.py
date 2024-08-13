import uuid
from datetime import timedelta
from typing import Optional

from django.contrib.gis.db import models
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from imagekit.models import ProcessedImageField
from pilkit.processors import ResizeToFit
from rest_framework.exceptions import ValidationError

from comments.models import Comment
from comments.models.commentable_notification_context import CommentNotificationMixin, CommentNotificationContext
from feed_posts.enums import VisibilityLevel
from feed_posts.helpers import upload_to_feed_post_images_directory
from openbook import settings
from openbook_auth.models import User, UserRole
from openbook_common.enums import ReactionType
from openbook_common.helpers import ExifRotate, generate_blurhash
from openbook_common.models import ModelWithUUID, LinkPreview
from openbook_common.types import LanguageCode
from openbook_common.utils.helpers import delete_file_field
from openbook_terms.models import Topic, FeedPostCategory


class FeedPost(CommentNotificationMixin, ModelWithUUID):
    title = models.CharField(max_length=settings.FEED_POST_TITLE_MAX_LENGTH, blank=True, null=True)

    slug = models.SlugField(max_length=settings.FEED_POST_SLUG_MAX_LENGTH, blank=False, null=False, unique=True)

    description = models.TextField(max_length=settings.FEED_POST_DESCRIPTION_MAX_LENGTH, blank=False, null=False)

    visibility = models.CharField(max_length=21, choices=VisibilityLevel.choices, default=VisibilityLevel.PUBLIC)

    topics = models.ManyToManyField(Topic, related_name="feed_posts", blank=True, db_index=True)

    category = models.ForeignKey(FeedPostCategory, on_delete=models.PROTECT, null=True)

    creator = models.ForeignKey(
        User,
        related_name="created_feed_posts",
        on_delete=models.CASCADE,
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

    priority_duration = models.PositiveIntegerField(
        default=0,
        help_text="Specifies how many days the post will remain at the top of the feed.",
    )

    @property
    def has_priority(self):
        if self.creator.role == UserRole.FOUNDER and self.category.slug == "founder-update":
            return self.created_at + timedelta(days=self.priority_duration) >= timezone.now()
        return False

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
