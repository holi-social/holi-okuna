import strawberry
import strawberry_django
from django.utils import translation
from django.utils.translation import get_language_from_request

from openbook_terms.models import SDG as SDG_MODEL
from openbook_terms.models import Skill as SkillModel
from openbook_terms.models import Topic as TopicModel
from openbook_terms.models import FeedPostCategory as FeedPostCategoryModel
from openbook_terms.models import InspirationPostCategory as InspirationPostCategoryModel


@strawberry_django.type(TopicModel)
class Topic:
    id: strawberry.auto
    slug: strawberry.auto
    is_discover_spaces_default: strawberry.auto

    @strawberry_django.field(only=["title"])
    def title(self, info) -> str:
        with translation.override(get_language_from_request(info.context.request)):
            return self.title


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


@strawberry_django.type(InspirationPostCategoryModel)
class InspirationPostCategory:
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
