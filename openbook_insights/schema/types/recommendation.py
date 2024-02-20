import strawberry
import strawberry_django

from openbook_insights.models import Recommendation as RecommendationModel
from openbook_posts.schema.types import LinkPreview


@strawberry_django.type(RecommendationModel)
class Recommendation:
    id: strawberry.auto
    category: strawberry.auto
    link: strawberry.auto
    link_preview: LinkPreview
    comment: strawberry.auto
