from generic_relations.relations import GenericRelatedField
from rest_framework import serializers

from comments.models import (
    CommentReaction,
    CommentUserMention,
    Comment,
)
from openbook_common.models import Badge, Language
from openbook_common.serializers import (
    CommonFollowRequestSerializer,
    CommonFollowSerializer,
    CommonHashtagSerializer,
    CommonPublicUserSerializer,
)
from openbook_common.serializers_fields.post import IsEncircledField
from openbook_common.serializers_fields.post_comment import PostCommentIsMutedField
from openbook_communities.models import Community, CommunityInvite
from openbook_notifications.models import (
    CommunityInviteNotification,
    CommunityNewPostNotification,
    ConnectionConfirmedNotification,
    ConnectionRequestNotification,
    FollowNotification,
    Notification,
    PostCommentNotification,
    PostCommentReactionNotification,
    PostCommentReplyNotification,
    PostCommentUserMentionNotification,
    PostUserMentionNotification,
)
from openbook_notifications.models.follow_request_approved_notification import (
    FollowRequestApprovedNotification,
)
from openbook_notifications.models.follow_request_notification import (
    FollowRequestNotification,
)
from openbook_notifications.models.post_reaction_notification import (
    PostReactionNotification,
)
from openbook_notifications.models.user_new_post_notification import (
    UserNewPostNotification,
)
from openbook_notifications.serializer_fields import ParentCommentField
from openbook_notifications.validators import notification_id_exists
from openbook_posts.models import (
    Post,
    PostImage,
    PostReaction,
    PostUserMention,
)


class ReadNotificationsSerializer(serializers.Serializer):
    max_id = serializers.IntegerField(
        required=False,
    )
    types = serializers.ListField(
        child=serializers.ChoiceField(
            choices=Notification.get_notification_types_values(),
            required=False,
        ),
        required=False,
    )


class UnreadNotificationsCountSerializer(serializers.Serializer):
    max_id = serializers.IntegerField(
        required=False,
    )
    types = serializers.ListField(
        child=serializers.ChoiceField(
            choices=Notification.get_notification_types_values(),
            required=False,
        ),
        required=False,
    )


class GetNotificationsSerializer(serializers.Serializer):
    count = serializers.IntegerField(required=False, max_value=20)
    max_id = serializers.IntegerField(
        required=False,
    )
    types = serializers.ListField(
        child=serializers.ChoiceField(
            choices=Notification.get_notification_types_values(),
            required=False,
        ),
        required=False,
    )


class NotificationsBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ("keyword", "keyword_description")


class PostImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(read_only=True)

    class Meta:
        model = PostImage
        fields = ("id", "image", "width", "height")


class PostCommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ("id", "name", "avatar", "cover", "color")


class NotificationPostSerializer(serializers.ModelSerializer):
    creator = CommonPublicUserSerializer()
    is_encircled = IsEncircledField()
    community = PostCommunitySerializer()
    # Temp backwards compat
    image = PostImageSerializer(many=False)

    class Meta:
        model = Post
        fields = (
            "id",
            "text",
            "creator",
            "created",
            "community",
            "is_closed",
            "is_encircled",
            # Temp backwards compat
            "image",
        )


class PostCommentLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = (
            "id",
            "code",
            "name",
        )


class NotificationPostCommentParentSerializer(serializers.ModelSerializer):
    commenter = CommonPublicUserSerializer()
    is_muted = PostCommentIsMutedField()
    language = PostCommentLanguageSerializer()

    class Meta:
        model = Comment
        fields = (
            "id",
            "commenter",
            "language",
            "text",
            "created",
            "is_edited",
            "is_muted",
        )


class NotificationPostCommentSerializer(serializers.ModelSerializer):
    commenter = CommonPublicUserSerializer()
    post = NotificationPostSerializer()
    parent_comment = NotificationPostCommentParentSerializer()
    is_muted = PostCommentIsMutedField()
    language = PostCommentLanguageSerializer()
    hashtags = CommonHashtagSerializer(many=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "commenter",
            "language",
            "text",
            "post",
            "created",
            "parent_comment",
            "is_muted",
            "hashtags",
        )


class PostCommentNotificationSerializer(serializers.ModelSerializer):
    post_comment = NotificationPostCommentSerializer()

    class Meta:
        model = PostCommentNotification
        fields = ("id", "post_comment")


class PostCommentReplyNotificationSerializer(serializers.ModelSerializer):
    post_comment = NotificationPostCommentSerializer()
    # TODO Remove after a couple of releases. Not needed anymore as the post_comment includes parent_comment
    parent_comment = ParentCommentField(parent_comment_serializer=NotificationPostCommentParentSerializer)

    class Meta:
        model = PostCommentReplyNotification
        fields = ("id", "post_comment", "parent_comment")


class PostCommentReactionSerializer(serializers.ModelSerializer):
    reactor = CommonPublicUserSerializer()
    reaction_type = serializers.CharField()
    post_comment = NotificationPostCommentSerializer()

    class Meta:
        model = CommentReaction
        fields = ("id", "reactor", "reaction_type", "post_comment", "created")


class PostCommentReactionNotificationSerializer(serializers.ModelSerializer):
    post_comment_reaction = PostCommentReactionSerializer()

    class Meta:
        model = PostCommentReactionNotification
        fields = ("id", "post_comment_reaction")


class PostReactionSerializer(serializers.ModelSerializer):
    reactor = CommonPublicUserSerializer()
    reaction_type = serializers.CharField()
    post = NotificationPostSerializer()

    class Meta:
        model = PostReaction
        fields = ("id", "reactor", "reaction_type", "post")


class PostReactionNotificationSerializer(serializers.ModelSerializer):
    post_reaction = PostReactionSerializer()

    class Meta:
        model = PostReactionNotification
        fields = ("id", "post_reaction")


class ConnectionRequestNotificationSerializer(serializers.ModelSerializer):
    connection_requester = CommonPublicUserSerializer()

    class Meta:
        model = ConnectionRequestNotification
        fields = ("id", "connection_requester")


class ConnectionConfirmedNotificationSerializer(serializers.ModelSerializer):
    connection_confirmator = CommonPublicUserSerializer()

    class Meta:
        model = ConnectionConfirmedNotification
        fields = ("id", "connection_confirmator")


class FollowNotificationSerializer(serializers.ModelSerializer):
    follower = CommonPublicUserSerializer()

    class Meta:
        model = FollowNotification
        fields = ("id", "follower")


class FollowRequestNotificationSerializer(serializers.ModelSerializer):
    follow_request = CommonFollowRequestSerializer()

    class Meta:
        model = FollowRequestNotification
        fields = ("id", "follow_request")


class FollowRequestApprovedNotificationSerializer(serializers.ModelSerializer):
    follow = CommonFollowSerializer()

    class Meta:
        model = FollowRequestApprovedNotification
        fields = ("id", "follow")


class CommunityInviteCommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ("id", "name", "avatar", "cover", "color")


class CommunityInviteSerializer(serializers.ModelSerializer):
    creator = CommonPublicUserSerializer()
    community = CommunityInviteCommunitySerializer()

    class Meta:
        model = CommunityInvite
        fields = ("id", "creator", "invited_user_id", "community")


class CommunityInviteNotificationSerializer(serializers.ModelSerializer):
    community_invite = CommunityInviteSerializer()

    class Meta:
        model = CommunityInviteNotification
        fields = ("id", "community_invite")


class CommunityNewPostNotificationSerializer(serializers.ModelSerializer):
    post = NotificationPostSerializer()

    class Meta:
        model = CommunityNewPostNotification
        fields = ("id", "post")


class UserNewPostNotificationSerializer(serializers.ModelSerializer):
    post = NotificationPostSerializer()

    class Meta:
        model = UserNewPostNotification
        fields = ("id", "post")


class PostUserMentionSerializer(serializers.ModelSerializer):
    post = NotificationPostSerializer()
    user = CommonPublicUserSerializer()

    class Meta:
        model = PostUserMention
        fields = (
            "id",
            "post",
            "user",
        )


class PostUserMentionNotificationSerializer(serializers.ModelSerializer):
    post_user_mention = PostUserMentionSerializer()

    class Meta:
        model = PostUserMentionNotification
        fields = (
            "id",
            "post_user_mention",
        )


class PostCommentUserMentionSerializer(serializers.ModelSerializer):
    post_comment = NotificationPostCommentSerializer()
    user = CommonPublicUserSerializer()

    class Meta:
        model = CommentUserMention
        fields = (
            "id",
            "post_comment",
            "user",
        )


class PostCommentUserMentionNotificationSerializer(serializers.ModelSerializer):
    post_comment_user_mention = PostCommentUserMentionSerializer()

    class Meta:
        model = PostCommentUserMentionNotification
        fields = (
            "id",
            "post_comment_user_mention",
        )


class GetNotificationsNotificationSerializer(serializers.ModelSerializer):
    content_object = GenericRelatedField(
        {
            PostCommentNotification: PostCommentNotificationSerializer(),
            PostCommentReplyNotification: PostCommentReplyNotificationSerializer(),
            PostCommentReactionNotification: PostCommentReactionNotificationSerializer(),
            PostReactionNotification: PostReactionNotificationSerializer(),
            ConnectionRequestNotification: ConnectionRequestNotificationSerializer(),
            ConnectionConfirmedNotification: ConnectionConfirmedNotificationSerializer(),
            FollowNotification: FollowNotificationSerializer(),
            FollowRequestNotification: FollowRequestNotificationSerializer(),
            FollowRequestApprovedNotification: FollowRequestApprovedNotificationSerializer(),
            PostCommentUserMentionNotification: PostCommentUserMentionNotificationSerializer(),
            PostUserMentionNotification: PostUserMentionNotificationSerializer(),
            CommunityNewPostNotification: CommunityNewPostNotificationSerializer(),
            UserNewPostNotification: UserNewPostNotificationSerializer(),
            CommunityInviteNotification: CommunityInviteNotificationSerializer(),
        }
    )

    class Meta:
        model = Notification
        fields = (
            "id",
            "notification_type",
            "content_object",
            "read",
            "created",
        )


class DeleteNotificationSerializer(serializers.Serializer):
    notification_id = serializers.UUIDField(required=True, validators=[notification_id_exists])


class ReadNotificationSerializer(serializers.Serializer):
    notification_id = serializers.UUIDField(required=True, validators=[notification_id_exists])
