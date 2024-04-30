import uuid
from typing import Optional, List

import strawberry
import strawberry_django
from strawberry.file_uploads import Upload

from feed_posts.enums import VisibilityLevel
from feed_posts.models import FeedPost
from openbook_auth.schema.types import User
from openbook_terms.schema.types import Topic, FeedPostCategory


@strawberry_django.type(FeedPost)
class FeedPost:
    id: strawberry.auto
    title: strawberry.auto
    slug: strawberry.auto
    description: strawberry.auto
    image: Optional[str]
    image_blurhash: Optional[str]
    visibility: VisibilityLevel
    topics: List[Optional[Topic]]
    category: FeedPostCategory
    creator: Optional[User]
    created_at: str


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
