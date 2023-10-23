import uuid
from typing import Optional

import strawberry
import strawberry_django

from openbook.settings import INSPIRATION_SPACE_ID
from openbook_common.schema.types import Paged
from openbook_posts.schema.types import Post
from openbook_posts.schema.utils import resolve_post
from openbook_posts.models import Post as PostModel
from openbook_auth.models import User as UserModel


@strawberry.type
class Query:
    @strawberry_django.field()
    def post_by_id(self, info, id: uuid.UUID) -> Optional[Post]:
        return resolve_post(info.context.request.user, id)

    @strawberry_django.field()
    def inspiration_posts(self, info, offset: int = 0, limit: int = 10) -> Paged[Post]:
        current_user: UserModel = info.context.request.user
        query = PostModel.objects.filter(
            PostModel.is_visible_query(current_user),
            status=PostModel.STATUS_PUBLISHED,
            is_public=True,
            community__id=uuid.UUID(INSPIRATION_SPACE_ID),
        )
        return Paged.of(query.order_by("-created"), offset, limit)
