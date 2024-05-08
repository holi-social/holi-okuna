import uuid
from typing import Optional, List

import strawberry
import strawberry_django
from strawberry.file_uploads import Upload

from feed_posts.enums import VisibilityLevel
from feed_posts.models import FeedPost as FeedPostModel, FeedPostReaction as FeedPostReactionModel
from feed_posts.services import FeedPostReactionService
from openbook_auth.schema.types import User
from openbook_common.schema.types import ReactionCounts
from openbook_terms.schema.types import Topic, FeedPostCategory


@strawberry_django.type(FeedPostModel)
class FeedPost:
    id: strawberry.auto
    title: strawberry.auto
    slug: strawberry.auto
    description: strawberry.auto
    image: Optional[str]
    image_blurhash: Optional[str]
    visibility: VisibilityLevel
    topics: Optional[List[Topic]]
    category: FeedPostCategory
    creator: Optional[User]
    created_at: str

    @strawberry_django.field()
    def reactions(self) -> ReactionCounts:
        reactions = FeedPostReactionService().count(post_id=self.pk)
        return ReactionCounts(**reactions)

    @strawberry_django.field()
    def my_reaction(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if not current_user.is_anonymous:
            try:
                reaction = FeedPostReactionService().get_reaction_by_user(feed_post=self, reactor=current_user)
                if reaction:
                    return ReactionCounts(**{reaction.reaction_type: 1})
            except FeedPostReactionModel.DoesNotExist:
                return ReactionCounts()
        return ReactionCounts()


@strawberry.input
class CreateFeedPostInput:
    title: str
    description: str
    image: Optional[Upload] = strawberry.UNSET
    visibility: VisibilityLevel
    topic_ids: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    category_id: uuid.UUID


@strawberry.input
class UpdateFeedPostInput:
    post_id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    image: Optional[Upload] = strawberry.UNSET
    visibility: Optional[VisibilityLevel] = strawberry.UNSET
    topic_ids: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    category_id: Optional[uuid.UUID] = strawberry.UNSET
