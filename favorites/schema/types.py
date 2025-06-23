from typing import Union, Annotated

import strawberry
import strawberry_django
from django.contrib.contenttypes.models import ContentType

from django.db.models import TextChoices as TextChoicesModel
from favorites.models import (
    UserFavorite as UserFavoriteModel,
    ExternalVolunteeringOpportunity as ExternalVolunteeringOpportunityModel,
)

from openbook_insights.schema.types import Insight
from openbook_communities.schema.types import Task


@strawberry_django.type(ExternalVolunteeringOpportunityModel)
class ExternalVolunteeringOpportunity:
    external_id: strawberry.auto


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
    ) -> Union[
        Annotated["Insight", strawberry.lazy("openbook_insights.schema.types")],
        Annotated["Task", strawberry.lazy("openbook_communities.schema.types")],
        ExternalVolunteeringOpportunity,
    ]:
        content_type_model = ContentType.objects.get(model=self.favoritable_type.model).model_class()
        return content_type_model.objects.get(pk=self.favoritable_id)


# Attention: the referenced content type models will be forwarded to registered users
# make sure their models handle authorization for private data in their strawberry django type fields
# also consider there could be relational data in nested queries (traversal attack)
@strawberry.enum
class FavoritableType(TextChoicesModel):
    INSIGHT = ("insight",)
    EXTERNAL_VOLUNTEERING_OPPORTUNITY = ("externalvolunteeringopportunity",)
    TASK = ("task",)
