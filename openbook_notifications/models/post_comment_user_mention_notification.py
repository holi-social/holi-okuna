from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_notifications.models.notification import Notification
from openbook_posts.models import PostComment


class PostCommentUserMentionNotification(ModelWithUUID):
    notification = GenericRelation(
        Notification, related_name="post_comment_user_mention_notifications"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="post_comment_mentions"
    )
    post_comment = models.ForeignKey(
        PostComment, on_delete=models.CASCADE, related_name="user_mentions"
    )

    @classmethod
    def create_post_comment_user_mention_notification(
        cls, post_comment_id, user_id, owner_id
    ):
        post_comment_user_mention_notification = cls.objects.create(
            post_comment_id=post_comment_id, user_id=user_id
        )
        Notification.create_notification(
            type=Notification.POST_COMMENT_USER_MENTION,
            content_object=post_comment_user_mention_notification,
            owner_id=owner_id,
        )
        return post_comment_user_mention_notification

    @classmethod
    def delete_post_comment_user_mention_notification(
        cls, post_comment_id, user_id, owner_id
    ):
        cls.objects.filter(
            post_comment_id=post_comment_id,
            user_id=user_id,
            notification__owner_id=owner_id,
        ).delete()
