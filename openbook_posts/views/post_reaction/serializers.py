from rest_framework import serializers

from openbook_auth.models import UserProfile, User
from openbook_common.models import Emoji
from openbook_posts.models import PostReaction
from openbook_posts.validators import post_id_exists, post_reaction_id_exists
from openbook_posts.views.post_comment.post_comment_reaction.serializers import (
    PostReactorProfileBadgeSerializer,
)


class DeletePostReactionSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
    post_reaction_id = serializers.UUIDField(
        validators=[post_reaction_id_exists],
        required=True,
    )


class PostReactorProfileSerializer(serializers.ModelSerializer):
    badges = PostReactorProfileBadgeSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = ("avatar", "badges")


class PostReactionReactorSerializer(serializers.ModelSerializer):
    profile = PostReactorProfileSerializer(many=False)

    class Meta:
        model = User
        fields = ("username", "profile", "id")


class PostReactionSerializer(serializers.ModelSerializer):
    reactor = PostReactionReactorSerializer(many=False)
    reaction_type = serializers.CharField()

    class Meta:
        model = PostReaction
        fields = ("reactor", "created", "reaction_type", "id")
