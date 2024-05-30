from django.db import models

from openbook_common.models import (
    ModelWithUUID,
)


class CommentUserMention(ModelWithUUID):
    user = models.ForeignKey("openbook_auth.User", on_delete=models.CASCADE, related_name="comment_mentions")
    post_comment = models.ForeignKey("comments.Comment", on_delete=models.CASCADE, related_name="user_mentions")

    class Meta:
        unique_together = (
            "user",
            "post_comment",
        )
        db_table = "openbook_posts_postcommentusermention"

    @classmethod
    def create_comment_user_mention(cls, user, comment):
        post_comment_user_mention = cls.objects.create(user=user, post_comment=comment)

        return post_comment_user_mention
