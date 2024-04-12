import strawberry
import strawberry_django

from openbook_common.schema.types import Paged
from openbook_terms.models import (
    SDG as SDGModel,
    Skill as SkillModel,
    Topic as TopicModel,
    FeedPostCategory as PostCategoryModel,
    InspirationPostCategory as InspirationPostCategoryModel,
)
from openbook_terms.schema.types import InspirationPostCategory, SDG, Skill, Topic, FeedPostCategory


@strawberry.type
class Query:
    @strawberry_django.field()
    def topics(self, offset: int = 0, limit: int = 50) -> Paged[Topic]:
        return Paged.of(TopicModel.objects.all().order_by("title"), offset, limit)

    @strawberry_django.field()
    def sdgs(self, offset: int = 0, limit: int = 50) -> Paged[SDG]:
        return Paged.of(SDGModel.objects.all().order_by("number"), offset, limit)

    @strawberry_django.field()
    def skills(self, offset: int = 0, limit: int = 50) -> Paged[Skill]:
        return Paged.of(SkillModel.objects.all().order_by("title"), offset, limit)

    @strawberry_django.field()
    def inspiration_post_categories(self, offset: int = 0, limit: int = 50) -> Paged[InspirationPostCategory]:
        return Paged.of(InspirationPostCategoryModel.objects.all().order_by("title"), offset, limit)

    @strawberry_django.field()
    def post_categories(self, offset: int = 0, limit: int = 50) -> Paged[FeedPostCategory]:
        return Paged.of(PostCategoryModel.objects.all().order_by("title"), offset, limit)
