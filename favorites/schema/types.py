from typing import Union, Annotated

import strawberry
import strawberry_django
from django.contrib.contenttypes.models import ContentType

from favorites.models import UserFavorite
from openbook_insights.schema.types import Insight, Quote, Recommendation, Initiative


@strawberry_django.type(UserFavorite)
class UserFavorite:
    id: strawberry.auto
    bookmark_id: strawberry.auto

    @strawberry_django.field()
    def bookmark_type(self) -> str:
        return self.bookmark_type.model.upper()

    @strawberry_django.field()
    def bookmark_item(
        self,
    ) -> Union[
        Annotated["Insight", strawberry.lazy("openbook_insights.schema.types")],
        Annotated["Quote", strawberry.lazy("openbook_insights.schema.types")],
        Annotated["Recommendation", strawberry.lazy("openbook_insights.schema.types")],
        Annotated["Initiative", strawberry.lazy("openbook_insights.schema.types")],
    ]:
        bookmark_type = ContentType.objects.get(model=self.bookmark_type.model).model_class()
        return bookmark_type.objects.get(pk=self.bookmark_id)
