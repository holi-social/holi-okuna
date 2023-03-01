from rest_framework import serializers

from openbook_common.models import Emoji, EmojiGroup
from openbook_common.validators import reaction_type_exists
from openbook_posts.validators import (
    post_id_exists,
    post_comment_id_exists,
    post_comment_id_exists_for_post_with_id,
)


class PostCommentReactionEmojiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emoji
        fields = (
            "id",
            "keyword",
            "image",
            "created",
        )


class PostCommentEmojiCountSerializer(serializers.Serializer):
    reaction_type = serializers.CharField(validators=[reaction_type_exists])
    count = serializers.IntegerField(
        required=True,
    )


class ReactToPostCommentSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
    post_comment_id = serializers.UUIDField(
        validators=[post_comment_id_exists],
        required=True,
    )
    reaction_type = serializers.CharField(
        validators=[reaction_type_exists],
        required=True,
    )

    def validate(self, data):
        post_comment_id_exists_for_post_with_id(post_comment_id=data["post_comment_id"], post_id=data["post_id"])
        return data


class GetPostCommentReactionsEmojiCountSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
    post_comment_id = serializers.UUIDField(
        validators=[post_comment_id_exists],
        required=True,
    )

    def validate(self, data):
        post_comment_id_exists_for_post_with_id(post_comment_id=data["post_comment_id"], post_id=data["post_id"])
        return data


class GetPostCommentReactionsSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
    post_comment_id = serializers.UUIDField(
        validators=[post_comment_id_exists],
        required=True,
    )
    max_id = serializers.IntegerField(
        required=False,
    )
    count = serializers.IntegerField(required=False, max_value=20)
    reaction_type = serializers.CharField(
        validators=[reaction_type_exists],
        required=False,
    )

    def validate(self, data):
        post_comment_id_exists_for_post_with_id(post_comment_id=data["post_comment_id"], post_id=data["post_id"])
        return data


class PostCommentReactionEmojiGroupSerializer(serializers.ModelSerializer):
    emojis = serializers.SerializerMethodField()

    def get_emojis(self, obj):
        emojis = obj.emojis.all().order_by("order")

        request = self.context["request"]
        return PostCommentReactionEmojiSerializer(emojis, many=True, context={"request": request}).data

    class Meta:
        model = EmojiGroup

        fields = (
            "id",
            "keyword",
            "color",
            "order",
            "emojis",
        )
