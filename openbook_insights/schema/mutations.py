import uuid

import strawberry
import structlog
from asgiref.sync import sync_to_async

from openbook_auth.utils import verify_authorized_user
from openbook_common.enums import ReactionType, ReactionAction
from openbook_insights.schema.types import Quote, Recommendation, Initiative
from openbook_insights.models import (
    Quote as QuoteModel,
    Recommendation as RecommendationModel,
    Initiative as InitiativeModel,
)

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def update_quote_reaction(
        self,
        info,
        quote_id: uuid.UUID,
        reaction_type: ReactionType,
        reaction_action: ReactionAction,
    ) -> Quote:
        current_user = verify_authorized_user(info)
        quote = QuoteModel.objects.get(id=quote_id)
        if reaction_action == ReactionAction.SET:
            quote.react(current_user, reaction_type)
        else:
            quote.clear_reaction(current_user, reaction_type)
        return quote

    @strawberry.mutation
    @sync_to_async
    def update_recommendation_reaction(
        self,
        info,
        recommendation_id: uuid.UUID,
        reaction_type: ReactionType,
        reaction_action: ReactionAction,
    ) -> Recommendation:
        current_user = verify_authorized_user(info)
        recommendation = RecommendationModel.objects.get(id=recommendation_id)
        if reaction_action == ReactionAction.SET:
            recommendation.react(current_user, reaction_type)
        else:
            recommendation.clear_reaction(current_user, reaction_type)
        return recommendation

    @strawberry.mutation
    @sync_to_async
    def update_initiative_reaction(
        self,
        info,
        initiative_id: uuid.UUID,
        reaction_type: ReactionType,
        reaction_action: ReactionAction,
    ) -> Initiative:
        current_user = verify_authorized_user(info)
        initiative = InitiativeModel.objects.get(id=initiative_id)
        if reaction_action == ReactionAction.SET:
            initiative.react(current_user, reaction_type)
        else:
            initiative.clear_reaction(current_user, reaction_type)
        return initiative
