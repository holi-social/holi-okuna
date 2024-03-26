from django.db import models
from django.db.models import Q
from django.utils import timezone

from openbook_auth.models import User
from openbook_common.enums import ReactionType
from openbook_common.models import (
    ModelWithUUID,
)


class CommentReaction(ModelWithUUID):
    post_comment = models.ForeignKey("Comment", on_delete=models.CASCADE, related_name="reactions")
    created = models.DateTimeField(editable=False)
    reactor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_comment_reactions")
    reaction_type = models.CharField(max_length=20, choices=ReactionType.choices)

    class Meta:
        unique_together = (
            "reactor",
            "post_comment",
        )
        db_table = "openbook_posts_postcommentreaction"

    @classmethod
    def create_reaction(cls, reactor, reaction_type, post_comment):
        CommentReaction.objects.filter(reactor=reactor, post_comment=post_comment).delete()
        return CommentReaction.objects.create(reactor=reactor, reaction_type=reaction_type, post_comment=post_comment)

    @classmethod
    def remove_reaction(cls, reactor, reaction_type, post_comment):
        return CommentReaction.objects.filter(
            reactor=reactor, reaction_type=reaction_type, post_comment=post_comment
        ).delete()

    @classmethod
    def count_reactions_for_post_with_id(cls, post_comment_id, reactor_id=None, reaction_type=None):
        count_query = Q(post_comment_id=post_comment_id, reactor__is_deleted=False)

        if reactor_id:
            count_query.add(Q(reactor_id=reactor_id), Q.AND)

        if reaction_type:
            count_query.add(Q(reaction_type=reaction_type), Q.AND)

        return cls.objects.filter(count_query).count()

    def save(self, *args, **kwargs):
        """On save, update timestamps"""
        if not self.created:
            self.created = timezone.now()
        return super(CommentReaction, self).save(*args, **kwargs)
