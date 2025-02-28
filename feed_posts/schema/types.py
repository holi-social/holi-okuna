import uuid
from typing import Optional, List, Annotated

import strawberry
import strawberry_django
from strawberry.file_uploads import Upload

from comments.models.enabled_commentable_type import EnabledCommentableType
from feed_posts.enums import VisibilityLevel, AspectRatio
from feed_posts.models import (
    FeedPost as FeedPostModel,
    FeedPostReaction as FeedPostReactionModel,
    FeedPostImage as FeedPostImageModel,
)
from feed_posts.services import FeedPostReactionService, FeedPostMentionService
from openbook_auth.schema.types import User
from openbook_common.schema.types import ReactionCounts, Paged, GeolocationPointInput, GeolocationPoint
from openbook_insights.schema.types import Insight
from openbook_posts.schema.types import LinkPreview, Post
from openbook_terms.schema.types import Topic, FeedPostCategory
from comments.models import Comment as CommentModel
from openbook_auth.models import UserBlock as UserBlockModel


@strawberry_django.type(FeedPostImageModel)
class FeedPostImage:
    id: strawberry.auto
    image: str
    image_blurhash: str
    order: int
    alt_text: Optional[str]
    aspect_ratio: Optional[AspectRatio]


@strawberry_django.type(FeedPostModel)
class FeedPost:
    id: strawberry.auto
    title: strawberry.auto
    slug: strawberry.auto
    description: strawberry.auto
    location: Optional[str]
    link_preview: Optional[LinkPreview]
    image: Annotated[
        Optional[str],
        strawberry.argument(description="This field is deprecated. Please use the new images field instead."),
    ]  # Can be removed after version 1.30.x
    image_blurhash: Annotated[
        Optional[str],
        strawberry.argument(description="This field is deprecated. Please use the new images field instead."),
    ]  # Can be removed after version 1.30.x
    visibility: VisibilityLevel
    topics: Annotated[
        Optional[List[Topic]],
        strawberry.argument(description="Deprecated since 1.52. Use topics_v2 instead."),
    ]
    topics_v2: Optional[List[str]]
    category: Optional[FeedPostCategory]
    creator: Optional[User]

    @strawberry_django.field()
    def created_at(self) -> str:
        return self.created_at.isoformat()

    @strawberry_django.field()
    def mentions(self) -> Optional[List[Optional[User]]]:
        return FeedPostMentionService().get_mentions(post_id=self.pk)

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

    @strawberry_django.field()
    def total_comments(self) -> int:
        return CommentModel.total_comments(commentable_id=self.id, commentable_type=EnabledCommentableType.FEED_POST)

    @strawberry_django.field()
    def commenters(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user

        commenters = CommentModel.get_commenters(
            commentable_id=self.id, commentable_type=EnabledCommentableType.FEED_POST, user=current_user
        )

        return UserBlockModel.paged(current_user, lambda user: user.id, commenters, offset, limit)

    @strawberry_django.field()
    def language(self) -> Optional[str]:
        return self.language_code

    @strawberry_django.field()
    def geolocation(self) -> Optional[GeolocationPoint]:
        return GeolocationPoint.from_point(self.geolocation)

    @strawberry_django.field()
    def images(self) -> Optional[List[Optional[FeedPostImage]]]:
        return self.images.all()


@strawberry.input
class FeedPostImageInput:
    image: Upload
    order: int
    alt_text: Optional[str] = strawberry.UNSET
    aspect_ratio: Optional[AspectRatio] = strawberry.UNSET


@strawberry.input
class CreateFeedPostInput:
    title: str
    description: str
    image: Optional[Upload] = (
        strawberry.UNSET
    )  # This field is deprecated. Please use the new images field instead. Remove it after version 1.30.x
    visibility: VisibilityLevel
    topic_ids: Optional[List[Optional[uuid.UUID]]] = strawberry_django.field(
        deprecation_reason="Deprecated since 1.52. Use topics_v2 instead."
    )
    topics_v2: Optional[List[str]] = strawberry.UNSET
    category_id: Optional[uuid.UUID] = strawberry.UNSET
    language: Optional[str] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    images: Optional[List[Optional[FeedPostImageInput]]] = strawberry.UNSET


@strawberry.input
class FeedPostImageMetadata:
    id: uuid.UUID
    order: int
    alt_text: Optional[str] = strawberry.UNSET
    aspect_ratio: Optional[AspectRatio] = strawberry.UNSET


@strawberry.input
class UpdateFeedPostInput:
    post_id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    image: Optional[Upload] = (
        strawberry.UNSET
    )  # This field is deprecated. Please use the new images field instead. Remove it after version 1.30.x
    visibility: Optional[VisibilityLevel] = strawberry.UNSET
    topic_ids: Optional[List[Optional[uuid.UUID]]] = strawberry_django.field(
        deprecation_reason="Deprecated since 1.52. Use topics_v2 instead."
    )
    topics_v2: Optional[List[str]] = strawberry.UNSET
    category_id: Optional[uuid.UUID] = strawberry.UNSET
    language: Optional[str] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    existing_images: Optional[List[Optional[FeedPostImageMetadata]]] = strawberry.UNSET
    new_images: Optional[List[Optional[FeedPostImageInput]]] = strawberry.UNSET


GenericPost = strawberry.union("GenericPost", (FeedPost, Post))


@strawberry.type
class FeedItem:
    feed_post: Optional[FeedPost]
    insight: Optional[Insight]
    space_post: Optional[Post]
