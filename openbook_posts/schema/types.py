import logging
import uuid
from typing import TYPE_CHECKING, Annotated, List, Optional, TypeVar

import strawberry
import strawberry_django
from django.db.models import Q
from strawberry.file_uploads import Upload

from comments.models import Comment as CommentModel
from comments.models import CommentReaction as CommentReactionModel
from openbook_auth.models import User as UserModel
from openbook_auth.models import UserBlock as UserBlockModel
from openbook_auth.schema.types import User
from openbook_common.models import LinkPreview as LinkPreviewModel
from openbook_common.schema.types import Paged, ReactionCounts
from openbook_communities.models import VisibilityType
from openbook_posts.models import Post as PostModel
from openbook_posts.models import PostImage as PostImageModel
from openbook_posts.models import PostReaction as PostReactionModel
from openbook_terms.schema.types import InspirationPostCategory

if TYPE_CHECKING:
    from openbook_communities.schema.types import Space

logger = logging.getLogger(__name__)

GenericType = TypeVar("GenericType")


@strawberry.input
class CreatePostCommentInput:
    post_id: uuid.UUID
    text: str


@strawberry.type
class CreatePostCommentOutput:
    post_comment: "PostComment"
    post_by_id: "Post"


@strawberry.input
class CreatePostInput:
    space_id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    text: str
    image: Optional[Upload] = strawberry.UNSET
    visibility: VisibilityType


@strawberry.input
class UpdatePostInput:
    post_id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    text: Optional[str] = strawberry.UNSET
    image: Optional[Upload] = strawberry.UNSET
    visibility: Optional[VisibilityType] = strawberry.UNSET


@strawberry_django.type(LinkPreviewModel)
class LinkPreview:
    id: strawberry.auto
    requested_url: strawberry.auto
    url: strawberry.auto
    title: strawberry.auto
    description: strawberry.auto
    type: strawberry.auto
    image: strawberry.auto
    site_name: strawberry.auto
    fetched_at: strawberry.auto
    icon: strawberry.auto

    @strawberry_django.field()
    def origin(self) -> str:
        return self.get_origin()


@strawberry_django.type(PostImageModel)
class PostImage:
    id: uuid.UUID
    width: int
    height: int
    url: str = strawberry_django.field(field_name="image")
    blurhash: Optional[str] = strawberry_django.field(field_name="image_blurhash")


@strawberry_django.type(PostModel)
class Post:
    id: strawberry.auto
    title: strawberry.auto
    text: strawberry.auto
    created: strawberry.auto
    modified: strawberry.auto
    comments_enabled: strawberry.auto
    mentions: List[Optional[User]]
    links: List[Optional[LinkPreview]]
    is_public: strawberry.auto
    space: Optional[Annotated["Space", strawberry.lazy("openbook_communities.schema.types")]] = (
        strawberry_django.field(field_name="community")
    )
    creator: User = strawberry_django.field(select_related="creator__profile")
    inspiration_post_category: Optional[InspirationPostCategory]

    @strawberry_django.field()
    def image(self) -> Optional[PostImage]:
        if hasattr(self, "image"):
            return self.image
        return None

    @strawberry_django.field()
    def comments(self, info) -> List[Optional["PostComment"]]:
        current_user = info.context.request.user
        all_comments = (
            CommentModel.objects.filter(post=self)
            .filter(CommentModel.is_visible_query(current_user))
            .order_by("created")
        )
        blocked_users = UserBlockModel.users_blocking_or_blocked(current_user)
        non_blocked_comments = [comment for comment in all_comments if comment.commenter.id not in blocked_users]
        return non_blocked_comments

    # this should be removed, once comments are paged
    @strawberry_django.field()
    def number_of_comments(self, info) -> int:
        current_user = info.context.request.user
        # count does not respect userblocks due to caching, this is intended for now
        return CommentModel.objects.filter(post=self).filter(CommentModel.is_visible_query(current_user)).count()

    @strawberry_django.field(description="A list of all users involved. Author of the post plus all commenters")
    def involved_users(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user
        involved_users = (
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_ignore_blocked_query())
            .filter(
                (Q(posts=self) & PostModel.is_visible_query(current_user, "posts"))
                | (Q(comments__post=self) & CommentModel.is_visible_query(current_user, "comments"))
            )
            .distinct()
        )
        return UserBlockModel.paged(current_user, lambda user: user.id, involved_users, offset, limit)

    @strawberry_django.field()
    def commenters(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user
        commenters = (
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_ignore_blocked_query())
            .filter(Q(comments__post=self) & CommentModel.is_visible_query(current_user, "comments"))
            .distinct()
        )
        return UserBlockModel.paged(current_user, lambda user: user.id, commenters, offset, limit)

    @strawberry_django.field()
    def reactions(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            reactions = PostModel.get_reaction_counts_for_post_with_id(self.pk)
        else:
            reactions = current_user.get_reaction_counts_for_post_with_id(self.pk)
        return ReactionCounts(**reactions)

    @strawberry_django.field(description="Only present, when the current user reacted to this post")
    def my_reaction(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if not current_user.is_anonymous:
            try:
                reaction = PostReactionModel.objects.filter(post=self, reactor=current_user).first()
                if reaction:
                    return ReactionCounts(**{reaction.reaction_type: 1})
            except PostReactionModel.DoesNotExist:
                return ReactionCounts()
        return ReactionCounts()


@strawberry_django.type(CommentModel)
class PostComment:
    id: strawberry.auto
    text: strawberry.auto
    created: strawberry.auto
    modified: strawberry.auto
    mentions: List[Optional[User]]
    links: List[Optional[LinkPreview]]
    post: Post = strawberry_django.field(field_name="commentable")
    creator: User = strawberry_django.field(field_name="commenter", select_related="commenter__profile")

    @strawberry_django.field()
    def reactions(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            reactions = CommentModel.get_reaction_counts(self.pk)
        else:
            reactions = current_user.get_reaction_counts_for_post_comment_with_id(self.pk)
        return ReactionCounts(**reactions)

    @strawberry_django.field(description="Only present, when the current user reacted to this post comment")
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
