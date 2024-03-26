from django.db import models

from openbook_auth.models import User
from openbook_common.models import (
    ModelWithUUID,
)
from openbook_common.utils.model_loaders import (
    get_post_comment_user_mention_notification_model,
)
from openbook_notifications.helpers import (
    send_post_comment_user_mention_push_notification,
)


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
            PostCommentUserMentionNotification = get_post_comment_user_mention_notification_model()
            PostCommentUserMentionNotification.create_post_comment_user_mention_notification(
                post_comment_user_mention_id=post_comment_user_mention.pk,
                owner_id=user.pk,
            )
            send_post_comment_user_mention_push_notification(post_comment_user_mention=post_comment_user_mention)
        return post_comment_user_mention
