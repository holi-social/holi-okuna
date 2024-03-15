import strawberry
import strawberry_django

from openbook_common.schema.types import ReactionCounts
from openbook_common.types import ReactableType
from openbook_insights.models import Initiative as InitiativeModel
from openbook_posts.schema.types import LinkPreview


@strawberry_django.type(InitiativeModel)
class Initiative:
    id: strawberry.auto
    link: strawberry.auto
    link_preview: LinkPreview
    category: strawberry.auto

    @strawberry_django.field()
    def reactions(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            reactions = InitiativeModel.get_reactions_count(self.pk)
        else:
            reactions = current_user.get_reactions_count(reactable_type=ReactableType.INITIATIVE, reactable_id=self.pk)
        return ReactionCounts(**reactions)

    @strawberry_django.field()
    def my_reaction(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if not current_user.is_anonymous:
            try:
                reaction = InitiativeModel.objects.filter(initiative=self, reactor=current_user).first()
                if reaction:
                    return ReactionCounts(**{reaction.reaction_type: 1})
            except InitiativeModel.DoesNotExist:
                return ReactionCounts()
        return ReactionCounts()
