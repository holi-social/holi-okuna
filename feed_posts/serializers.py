from rest_framework import serializers

from feed_posts.enums import VisibilityLevel
from feed_posts.validators import (
    validate_topic_exists_by_id,
    validate_feed_post_category_exists_by_id,
    feed_post_exists,
)
from openbook import settings
from openbook_common.serializers_fields.request import RestrictedImageFileSizeField


class CreateFeedPostSerializer(serializers.Serializer):
    title = serializers.CharField(
        min_length=settings.FEED_POST_TITLE_MIN_LENGTH,
        max_length=settings.FEED_POST_TITLE_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )

    description = serializers.CharField(
        min_length=settings.FEED_POST_DESCRIPTION_MIN_LENGTH,
        max_length=settings.FEED_POST_DESCRIPTION_MAX_LENGTH,
        required=True,
    )

    visibility = serializers.ChoiceField(required=True, choices=VisibilityLevel.choices)

    topic_ids = serializers.ListField(
        max_length=settings.FEED_POST_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[validate_topic_exists_by_id]),
    )

    category_id = serializers.UUIDField(required=True, validators=[validate_feed_post_category_exists_by_id])

    image = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.FEED_POST_IMAGE_MAX_SIZE,
    )


class UpdateFeedPostSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[feed_post_exists],
        required=True,
    )
    title = serializers.CharField(
        min_length=settings.FEED_POST_TITLE_MIN_LENGTH,
        max_length=settings.FEED_POST_TITLE_MAX_LENGTH,
        required=False,
    )

    description = serializers.CharField(
        min_length=settings.FEED_POST_DESCRIPTION_MIN_LENGTH,
        max_length=settings.FEED_POST_DESCRIPTION_MAX_LENGTH,
        required=False,
    )

    visibility = serializers.ChoiceField(required=False, choices=VisibilityLevel.choices)

    topic_ids = serializers.ListField(
        max_length=settings.FEED_POST_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[validate_topic_exists_by_id]),
    )

    category_id = serializers.UUIDField(required=False, validators=[validate_feed_post_category_exists_by_id])

    image = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.FEED_POST_IMAGE_MAX_SIZE,
        allow_null=True,
    )
