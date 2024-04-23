from django.db import models

from openbook_auth.models import User
from openbook_common.models import (
    ModelWithUUID,
)
from openbook_notifications.notifications import PostCommentMentionNotification
from openbook_notifications.payloads import PostCommentMentionPayload, NotificationType


class CommentUserMention(ModelWithUUID):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comment_mentions")
    post_comment = models.ForeignKey("Comment", on_delete=models.CASCADE, related_name="user_mentions")

    class Meta:
        unique_together = (
            "user",
            "post_comment",
        )
        db_table = "openbook_posts_postcommentusermention"

    @classmethod
    def create_comment_user_mention(cls, user, comment, notify=True):
        post_comment_user_mention = cls.objects.create(user=user, post_comment=comment)

        if notify:
            notification = PostCommentMentionNotification(
                mentions=[str(mentioned_user.username) for mentioned_user in comment.mentions.all()],
                payload=PostCommentMentionPayload(
                    post_comment=comment,
                    notification_type=NotificationType.POST_COMMENT_MENTION.value,
                ),
            )
            notification.send()

        return post_comment_user_mention
