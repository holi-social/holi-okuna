import strawberry
import strawberry_django

from openbook_common.schema.types import Paged
from openbook_terms.models import (
    FeedPostCategory as FeedPostCategoryModel,
)
from openbook_terms.schema.types import FeedPostCategory


@strawberry.type
class Query:
    @strawberry_django.field()
    def feed_post_categories(self, offset: int = 0, limit: int = 50) -> Paged[FeedPostCategory]:
        return Paged.of(FeedPostCategoryModel.objects.all().order_by("title"), offset, limit)
