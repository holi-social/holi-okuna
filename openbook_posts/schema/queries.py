import uuid
from typing import Optional

import strawberry
import strawberry_django

from openbook_common.schema.types import Paged
from openbook_posts.schema.types import Post
from openbook_posts.schema.utils import resolve_post


@strawberry.type
class Query:
    @strawberry_django.field()
    def post_by_id(self, info, id: uuid.UUID) -> Optional[Post]:
        return resolve_post(info.context.request.user, id)

    @strawberry_django.field()
    def inspiration_posts(self, info, offset: int = 0, limit: int = 10) -> Paged[Post]:
        return Paged.empty()
