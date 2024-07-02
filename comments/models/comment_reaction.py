from django.db import models
from django.utils import timezone

from openbook_auth.models import User
from openbook_common.enums import ReactionType
from openbook_common.models import (
    ModelWithUUID,
)


class CommentReaction(ModelWithUUID):
    post_comment = models.ForeignKey("Comment", on_delete=models.CASCADE, related_name="reactions")
    created = models.DateTimeField(editable=False)
    reactor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comment_reactions")
    reaction_type = models.CharField(max_length=20, choices=ReactionType.choices)

    class Meta:
        unique_together = (
            "reactor",
            "post_comment",
        )
        db_table = "openbook_posts_postcommentreaction"

    @classmethod
    def create_reaction(cls, reactor, reaction_type, comment):
        CommentReaction.objects.filter(reactor=reactor, post_comment=comment).delete()
        return CommentReaction.objects.create(reactor=reactor, reaction_type=ReactionType.get_value(reaction_type), post_comment=comment)

    @classmethod
    def remove_reaction(cls, reactor, reaction_type, comment):
        return CommentReaction.objects.filter(
            reactor=reactor, reaction_type=ReactionType.get_value(reaction_type), post_comment=comment
        ).delete()

    def save(self, *args, **kwargs):
        """On save, update timestamps"""
        if not self.created:
            self.created = timezone.now()
        return super(CommentReaction, self).save(*args, **kwargs)
