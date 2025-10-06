from uuid import UUID

import strawberry
import strawberry_django
from django.utils import translation
from django.utils.translation import get_language_from_request

from openbook_terms.models import FeedPostCategory as FeedPostCategoryModel
from openbook_terms.models import SDG as SDG_MODEL
from openbook_terms.models import Skill as SkillModel


# This is still needed for backwards compatibility for "Wir sind der Osten"
@strawberry.type()
class Topic:
    slug: str
    title: str


@strawberry_django.type(SDG_MODEL)
class SDG:
    id: strawberry.auto
    slug: strawberry.auto
    number: strawberry.auto

    @strawberry_django.field(only=["title"])
    def title(self, info) -> str:
        with translation.override(get_language_from_request(info.context.request)):
            return self.title


@strawberry_django.type(SkillModel)
class Skill:
    id: strawberry.auto
    slug: strawberry.auto

    @strawberry_django.field(only=["title"])
    def title(self, info) -> str:
        with translation.override(get_language_from_request(info.context.request)):
            return self.title


@strawberry_django.type(FeedPostCategoryModel)
class FeedPostCategory:
    id: strawberry.auto
    idx: strawberry.auto
    slug: strawberry.auto
    is_enabled: strawberry.auto

    @strawberry_django.field(only=["title"])
    def title(self, info) -> str:
        with translation.override(get_language_from_request(info.context.request)):
            return self.title

    @strawberry_django.field(only=["label"])
    def label(self, info) -> str:
        with translation.override(get_language_from_request(info.context.request)):
            return self.label


@strawberry.type()
class InspirationPostCategory:
    id: UUID
    slug: str
    title: str
