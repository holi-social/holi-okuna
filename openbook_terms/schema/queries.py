import strawberry
import strawberry_django

from openbook_common.schema.types import Paged
from openbook_terms.models import (
    SDG as SDG_MODEL,
    Skill as SkillModel,
    Topic as TopicModel,
    FeedPostCategory as FeedPostCategoryModel,
)
from openbook_terms.schema.types import SDG, Skill, Topic, FeedPostCategory


@strawberry.type
class Query:
    @strawberry_django.field(
        deprecation_reason="Deprecated since 1.52. Use V2 instead, which is now a static hard coded set of slugs."
    )
    def topics(self, offset: int = 0, limit: int = 50) -> Paged[Topic]:
        return Paged.of(TopicModel.objects.all().order_by("title"), offset, limit)

    @strawberry_django.field(deprecation_reason="Deprecated since 1.53.")
    def sdgs(self, offset: int = 0, limit: int = 50) -> Paged[SDG]:
        return Paged.of(SDG_MODEL.objects.all().order_by("number"), offset, limit)

    @strawberry_django.field(
        deprecation_reason="Deprecated since 1.52. Use V2 instead, which is now a static hard coded set of slugs."
    )
    def skills(self, offset: int = 0, limit: int = 50) -> Paged[Skill]:
        return Paged.of(SkillModel.objects.all().order_by("title"), offset, limit)

    @strawberry_django.field()
    def feed_post_categories(self, offset: int = 0, limit: int = 50) -> Paged[FeedPostCategory]:
        return Paged.of(FeedPostCategoryModel.objects.all().order_by("title"), offset, limit)
