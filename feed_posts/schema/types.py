import uuid
from typing import Optional, List

import strawberry
import strawberry_django

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
    visibility: VisibilityLevel
    topics: List[Optional[Topic]]
    category: FeedPostCategory
    creator: Optional[User]
    created_at: str


@strawberry.input
class CreateFeedPostInput:
    title: str
    description: str
    visibility: VisibilityLevel
    topics: List[Optional[uuid.UUID]]
    category_id: uuid.UUID
