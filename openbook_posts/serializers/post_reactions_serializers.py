from rest_framework import serializers

from openbook_common.models import Emoji, EmojiGroup
from openbook_common.validators import reaction_type_exists
from openbook_posts.validators import post_id_exists


class PostReactionEmojiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emoji
        fields = (
            "id",
            "keyword",
            "image",
            "created",
        )


class PostEmojiCountSerializer(serializers.Serializer):
    reaction_type = serializers.CharField(validators=[reaction_type_exists])
    count = serializers.IntegerField(
        required=True,
    )


class ReactToPostSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
    reaction_type = serializers.CharField(
        validators=[reaction_type_exists],
        required=True,
    )


class GetPostReactionsEmojiCountSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )


class GetPostReactionsSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
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


class PostReactionEmojiGroupSerializer(serializers.ModelSerializer):
    emojis = serializers.SerializerMethodField()

    def get_emojis(self, obj):
        emojis = obj.emojis.all().order_by("order")

        request = self.context["request"]
        return PostReactionEmojiSerializer(emojis, many=True, context={"request": request}).data

    class Meta:
        model = EmojiGroup

        fields = (
            "id",
            "keyword",
            "color",
            "order",
            "emojis",
        )
