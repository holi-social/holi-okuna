import strawberry
import strawberry_django

from openbook_insights.models import Discussion as DiscussionModel


@strawberry_django.type(DiscussionModel)
class Discussion:
    id: strawberry.auto
    question: strawberry.auto
