from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_notifications.models.notification import Notification
from openbook_posts.models import Post


class PostUserMentionNotification(ModelWithUUID):
    notification = GenericRelation(
        Notification, related_name="post_user_mention_notifications"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    @classmethod
    def create_post_user_mention_notification(cls, post_id, user_id, owner_id):
        post_user_mention_notification = cls.objects.create(
            post_id=post_id, user_id=user_id
        )
        Notification.create_notification(
            type=Notification.POST_USER_MENTION,
            content_object=post_user_mention_notification,
            owner_id=owner_id,
        )
        return post_user_mention_notification

    @classmethod
    def delete_post_user_mention_notification(cls, post_id, user_id, owner_id):
        cls.objects.filter(
            post_id=post_id, user_id=user_id, notification__owner_id=owner_id
        ).delete()
