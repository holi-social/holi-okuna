from django.db import models

from openbook_auth.models import User
from openbook_common.models import (
    ModelWithUUID,
)


class CommentMute(ModelWithUUID):
    post_comment = models.ForeignKey("Comment", on_delete=models.CASCADE, related_name="mutes")
    muter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_comment_mutes")

    class Meta:
        unique_together = (
            (
                "post_comment",
                "muter",
            ),
        )
        db_table = "openbook_posts_postcommentmute"

    @classmethod
    def create_post_comment_mute(cls, post_comment_id, muter_id):
        return cls.objects.create(post_comment_id=post_comment_id, muter_id=muter_id)
