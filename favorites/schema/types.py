from typing import Union, Annotated

import strawberry
import strawberry_django
from django.contrib.contenttypes.models import ContentType

from django.db.models import TextChoices as TextChoicesModel
from favorites.models import UserFavorite as UserFavoriteModel

from openbook_insights.schema.types import Insight


@strawberry_django.type(UserFavoriteModel)
class UserFavorite:
    id: strawberry.auto
    favoritable_id: strawberry.auto

    @strawberry_django.field()
    def favoritable_type(self) -> str:
        return self.favoritable_type.model.upper()

    @strawberry_django.field()
    def favoritable(
        self,
    ) -> Union[Annotated["Insight", strawberry.lazy("openbook_insights.schema.types")],]:
        content_type_model = ContentType.objects.get(model=self.favoritable_type.model).model_class()
        return content_type_model.objects.get(pk=self.favoritable_id)


@strawberry.enum
class FavoritableType(TextChoicesModel):
    INSIGHT = ("insight",)
