from django.conf import settings
from rest_framework import serializers

from comments.schema.types import CommentableType
from comments.validators import comment_text_validators


class CommentSerializer(serializers.Serializer):
    commentable_type = serializers.ChoiceField(
        CommentableType,
        required=True,
    )
    commentable_id = serializers.UUIDField(
        required=True,
    )
    text = serializers.CharField(
        max_length=settings.POST_COMMENT_MAX_LENGTH,
        required=True,
        validators=comment_text_validators,
    )
    parent_comment_id = serializers.UUIDField(
        required=False,
    )
