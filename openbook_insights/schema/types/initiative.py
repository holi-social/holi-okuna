import strawberry
import strawberry_django

from openbook_auth.schema.types import User
from openbook_common.schema.types import ReactionCounts, Paged
from openbook_common.types import ReactableType
from openbook_insights.models import (
    Initiative as InitiativeModel,
    InitiativeReaction as InitiativeReactionModel,
    InitiativeReaction,
)
from openbook_posts.schema.types import LinkPreview
from openbook_auth.models import User as UserModel


@strawberry_django.type(InitiativeModel)
class Initiative:
    id: strawberry.auto
    link: strawberry.auto
    link_preview: LinkPreview
    category: strawberry.auto
    comment: strawberry.auto

    @strawberry_django.field()
    def reactions(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            reactions = InitiativeModel.get_reactions_count(self.pk)
        else:
            reactions = current_user.get_reactions_count(reactable_type=ReactableType.INITIATIVE, reactable_id=self.pk)
        return ReactionCounts(**reactions)

    @strawberry_django.field()
    def reactors(self, offset: int = 0, limit: int = 10) -> Paged[User]:
        reactor_ids = (
            InitiativeReaction.objects.filter(initiative__id=self.pk).values_list("reactor", flat=True).distinct()
        )
        reactors = UserModel.objects.select_related("profile").filter(id__in=reactor_ids)
        return Paged.of(reactors, offset, limit)

    @strawberry_django.field()
    def my_reaction(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if not current_user.is_anonymous:
            try:
                reaction = InitiativeReactionModel.objects.filter(initiative=self, reactor=current_user).first()
                if reaction:
                    return ReactionCounts(**{reaction.reaction_type: 1})
            except InitiativeReactionModel.DoesNotExist:
                return ReactionCounts()
        return ReactionCounts()
