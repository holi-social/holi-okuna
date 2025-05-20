from rest_framework import serializers

from feed_posts.enums import VisibilityLevel, AspectRatio
from feed_posts.validators import (
    validate_topic_exists_by_id,
    validate_feed_post_category_exists_by_id,
    feed_post_exists,
)
from openbook import settings
from openbook_common.serializers import GeolocationPointSerializer
from openbook_common.serializers_fields.request import RestrictedImageFileSizeField
from openbook_common.types import LanguageCode
from openbook_common.validators import sanitize_text, topic_v2_exists


class FeedPostImageSerializer(serializers.Serializer):
    image = RestrictedImageFileSizeField(
        allow_empty_file=False,
        max_upload_size=settings.FEED_POST_IMAGE_MAX_SIZE,
        required=True,
    )
    order = serializers.IntegerField(required=True)
    alt_text = serializers.CharField(
        required=False, max_length=settings.CONTENT_IMAGE_ALT_TEXT_MAX_LENGTH, allow_blank=True
    )
    aspect_ratio = serializers.ChoiceField(required=False, choices=AspectRatio.choices)


class FeedPostImageMetadataSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=True)
    order = serializers.IntegerField(required=True)
    alt_text = serializers.CharField(
        required=False, max_length=settings.CONTENT_IMAGE_ALT_TEXT_MAX_LENGTH, allow_blank=True
    )
    aspect_ratio = serializers.ChoiceField(required=False, choices=AspectRatio.choices)


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
        validators=[sanitize_text],
    )
    visibility = serializers.ChoiceField(required=True, choices=VisibilityLevel.choices)
    topic_ids = serializers.ListField(
        max_length=settings.FEED_POST_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[validate_topic_exists_by_id]),
    )
    topics_v2 = serializers.ListField(
        max_length=settings.FEED_POST_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.CharField(validators=[topic_v2_exists]),
    )
    category_id = serializers.UUIDField(
        required=False, allow_null=True, validators=[validate_feed_post_category_exists_by_id]
    )
    image = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.FEED_POST_IMAGE_MAX_SIZE,
    )
    images = FeedPostImageSerializer(many=True, required=False, allow_null=True)
    language = serializers.CharField(max_length=2, required=False, allow_blank=True)
    location = serializers.CharField(
        max_length=settings.APPOINTMENT_LOCATION_MAX_LENGTH,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    geolocation = GeolocationPointSerializer(required=False)
    image_urls = serializers.ListField(
        required=False,
        allow_null=True,
    )
    aspect_ratio = serializers.ChoiceField(required=False, choices=AspectRatio.choices)


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
        validators=[sanitize_text],
    )
    visibility = serializers.ChoiceField(required=False, choices=VisibilityLevel.choices)
    topic_ids = serializers.ListField(
        max_length=settings.FEED_POST_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[validate_topic_exists_by_id]),
    )
    topics_v2 = serializers.ListField(
        max_length=settings.FEED_POST_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.CharField(validators=[topic_v2_exists]),
    )
    category_id = serializers.UUIDField(
        required=False, allow_null=True, validators=[validate_feed_post_category_exists_by_id]
    )
    image = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.FEED_POST_IMAGE_MAX_SIZE,
        allow_null=True,
    )
    language = serializers.CharField(max_length=2, required=False, allow_blank=True, default=LanguageCode.ENGLISH)
    location = serializers.CharField(
        max_length=settings.APPOINTMENT_LOCATION_MAX_LENGTH,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    geolocation = GeolocationPointSerializer(required=False)
    existing_images = FeedPostImageMetadataSerializer(many=True, required=False, allow_null=True)
    new_images = FeedPostImageSerializer(many=True, required=False, allow_null=True)
    image_urls = serializers.ListField(
        required=False,
        allow_null=True,
    )
    aspect_ratio = serializers.ChoiceField(required=False, choices=AspectRatio.choices)
