from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from comments.models import Comment
from openbook_common.models import ModelWithUUID
from openbook_notifications.models.notification import Notification


class PostCommentReplyNotification(ModelWithUUID):
    notification = GenericRelation(Notification, related_name="post_comment_reply_notifications")
    post_comment = models.ForeignKey(Comment, on_delete=models.CASCADE)

    @classmethod
    def create_post_comment_reply_notification(cls, post_comment_id, owner_id):
        post_comment_reply_notification = cls.objects.create(post_comment_id=post_comment_id)
        Notification.create_notification(
            type=Notification.POST_COMMENT_REPLY,
            content_object=post_comment_reply_notification,
            owner_id=owner_id,
        )
        return post_comment_reply_notification

    @classmethod
    def delete_post_comment_reply_notification(cls, post_comment_id, owner_id):
        cls.objects.filter(post_comment_id=post_comment_id, notification__owner_id=owner_id).delete()

    @classmethod
    def delete_post_comment_reply_notifications(cls, post_comment_id):
        cls.objects.filter(post_comment_id=post_comment_id).delete()

    def get_options(self):
        return {"post_comment": self.post_comment, "user": self.post_comment.commenter}
