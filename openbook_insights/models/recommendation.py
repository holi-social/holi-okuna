from django.db.models import (
    URLField,
    TextField,
    CASCADE,
    CharField,
    ForeignKey,
    SET_NULL,
    DateTimeField,
    Q,
)
from django.utils import timezone

from openbook_auth.models import User, get_reactions
from openbook_common.enums import ReactionType
from openbook_common.models import ModelWithUUID, LinkPreview
from openbook_common.validators import url_safety_validator
from openbook_insights.models.external_content import ExternalContentCategory
from openbook_insights.models.insight import Insight


class Recommendation(ModelWithUUID):
    insight = ForeignKey(Insight, on_delete=CASCADE, related_name="recommendations")

    category = CharField(choices=ExternalContentCategory.choices, max_length=255, null=False, blank=False)
    link = URLField(null=False, blank=False, validators=[url_safety_validator])
    link_preview = ForeignKey(LinkPreview, on_delete=SET_NULL, null=True)
    comment = TextField(null=False, blank=False, verbose_name="Why I recommend this content")

    def react(self, reactor, reaction_type):
        return RecommendationReaction.create_reaction(
            reactor=reactor, reaction_type=reaction_type, recommendation=self
        )

    def clear_reaction(self, reactor, reaction_type):
        return RecommendationReaction.remove_reaction(
            reactor=reactor, reaction_type=reaction_type, recommendation=self
        )

    def save(self, *args, **kwargs):
        if not self.link_preview:
            self.link_preview = LinkPreview.from_url(self.link)

        if self.link != self.link_preview.requested_url:
            self.link_preview.delete()
            self.link_preview = LinkPreview.from_url(self.link)

        super().save(*args, **kwargs)

    @classmethod
    def get_reactions_count(cls, recommendation_id, reaction_type=None, reactor_id=None):
        reactions_query = Q(
            recommendation_id=recommendation_id,
        )

        if reaction_type:
            reactions_query.add(Q(reaction_type=reaction_type), Q.AND)

        if reactor_id:
            reactions_query.add(Q(reactor__id=reactor_id), Q.AND)

        return get_reactions(RecommendationReaction, reactions_query)


class RecommendationReaction(ModelWithUUID):
    recommendation = ForeignKey(Recommendation, on_delete=CASCADE, related_name="reactions")
    created = DateTimeField(editable=False)
    reactor = ForeignKey(User, on_delete=CASCADE, related_name="recommendation_reactions")
    reaction_type = CharField(max_length=20, choices=ReactionType.choices)

    class Meta:
        unique_together = (
            "reactor",
            "recommendation",
        )

    @classmethod
    def create_reaction(cls, reactor, reaction_type, recommendation):
        RecommendationReaction.objects.filter(reactor=reactor, recommendation=recommendation).delete()
        return RecommendationReaction.objects.create(
            reactor=reactor, reaction_type=reaction_type, recommendation=recommendation
        )

    @classmethod
    def remove_reaction(cls, reactor, reaction_type, recommendation):
        return RecommendationReaction.objects.filter(
            reactor=reactor, reaction_type=reaction_type, recommendation=recommendation
        ).delete()

    @classmethod
    def count_reactions(cls, recommendation_id, reactor_id=None, reaction_type=None):
        count_query = Q(recommendation_id=recommendation_id, reactor__is_deleted=False)

        if reactor_id:
            count_query.add(Q(reactor_id=reactor_id), Q.AND)

        if reaction_type:
            count_query.add(Q(reaction_type=reaction_type), Q.AND)

        return cls.objects.filter(count_query).count()

    def save(self, *args, **kwargs):
        if not self.created:
            self.created = timezone.now()
        return super(RecommendationReaction, self).save(*args, **kwargs)
