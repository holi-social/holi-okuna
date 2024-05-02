import logging
import uuid
from typing import List, Optional

import strawberry
import strawberry_django

from comments.models.commentable import CommentableType
from comments.models import Comment as CommentModel
from comments.models import CommentReaction as CommentReactionModel
from openbook_auth.schema.types import User
from openbook_common.enums import ReactionType
from openbook_common.schema.types import ReactionCounts
from openbook_posts.schema.types import LinkPreview

logger = logging.getLogger(__name__)


@strawberry.input
class CreateCommentInput:
    commentable_type: CommentableType
    commentable_id: uuid.UUID
    text: str
    parent_comment_id: Optional[uuid.UUID] = strawberry.UNSET


@strawberry.input
class CommentReactionInput:
    comment_id: uuid.UUID
    reaction_type: ReactionType


@strawberry_django.type(CommentModel)
class Comment:
    id: strawberry.auto
    text: strawberry.auto
    created: strawberry.auto
    modified: strawberry.auto
    mentions: List[Optional[User]]
    links: List[Optional[LinkPreview]]
    creator: User = strawberry_django.field(field_name="commenter", select_related="commenter__profile")
    parent_comment_id: Optional[uuid.UUID]
    replies: Optional[List["Comment"]]

    @strawberry_django.field()
    def reactions(self, info) -> ReactionCounts:
        return ReactionCounts(**self.reaction_counts_by_type())

    @strawberry_django.field
    def my_reaction(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if not current_user.is_anonymous:
            try:
                reaction = CommentReactionModel.objects.filter(post_comment=self, reactor=current_user).first()
                if reaction:
                    return ReactionCounts(**{reaction.reaction_type: 1})
            except CommentReactionModel.DoesNotExist:
                return ReactionCounts()
        return ReactionCounts()

    @strawberry_django.field
    def total_replies(self, info) -> int:
        return self.count_replies()
