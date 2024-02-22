import strawberry
import strawberry_django

from openbook_insights.models import Quote as QuoteModel
from openbook_posts.schema.types import LinkPreview


@strawberry_django.type(QuoteModel)
class Quote:
    id: strawberry.auto
    quote: strawberry.auto

    quote_author: strawberry.auto
    quote_author_profession: strawberry.auto

    link: strawberry.auto
    link_preview: LinkPreview
    category: strawberry.auto

    comment: strawberry.auto
