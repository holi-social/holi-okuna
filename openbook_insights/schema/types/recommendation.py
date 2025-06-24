import strawberry
import strawberry_django

from openbook_auth.models import User as UserModel
from openbook_auth.schema.types import User
from openbook_common.schema.types import ReactionCounts, Paged
from openbook_common.types import ReactableType
from openbook_insights.models import (
    Recommendation as RecommendationModel,
    RecommendationReaction as RecommendationReactionModel,
)
from openbook_posts.schema.types import LinkPreview


@strawberry_django.type(RecommendationModel)
class Recommendation:
    id: strawberry.auto
    category: strawberry.auto
    link: strawberry.auto
    link_preview: LinkPreview
    comment: strawberry.auto

    @strawberry_django.field()
    def reactions(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            reactions = RecommendationModel.get_reactions_count(self.pk)
        else:
            reactions = current_user.get_reactions_count(
                reactable_type=ReactableType.RECOMMENDATION, reactable_id=self.pk
            )
        return ReactionCounts(**reactions)

    @strawberry_django.field()
    def reactors(self, offset: int = 0, limit: int = 10) -> Paged[User]:
        reactor_ids = (
            RecommendationReactionModel.objects.filter(recommendation__id=self.pk)
            .values_list("reactor", flat=True)
            .distinct()
        )
        reactors = UserModel.objects.select_related("profile").filter(id__in=reactor_ids)
        return Paged.of(reactors, offset, limit)

    @strawberry_django.field()
    def my_reaction(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if not current_user.is_anonymous:
            try:
                reaction = RecommendationReactionModel.objects.filter(
                    recommendation=self, reactor=current_user
                ).first()
                if reaction:
                    return ReactionCounts(**{reaction.reaction_type: 1})
            except RecommendationReactionModel.DoesNotExist:
                return ReactionCounts()
        return ReactionCounts()
