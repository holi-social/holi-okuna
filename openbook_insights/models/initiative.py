import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from openbook_auth.models import get_reactions, User
from openbook_common.enums import ReactionType
from openbook_common.models import ModelWithUUID, LinkPreview
from openbook_common.validators import url_safety_validator
from openbook_insights.models import Insight, ExternalContentCategory


class Initiative(ModelWithUUID):
    insight = models.ForeignKey(Insight, on_delete=models.CASCADE, related_name="initiatives")

    category = models.CharField(max_length=255, choices=ExternalContentCategory.choices)

    link = models.URLField(null=False, blank=False, validators=[url_safety_validator])
    link_preview = models.ForeignKey(LinkPreview, null=True, blank=True, on_delete=models.PROTECT)

    comment = models.TextField(null=True, blank=True, verbose_name="Why I recommend this initiative")

    def react(self, reactor, reaction_type):
        return InitiativeReaction.create_reaction(reactor=reactor, reaction_type=reaction_type, initiative=self)

    def clear_reaction(self, reactor, reaction_type):
        return InitiativeReaction.remove_reaction(reactor=reactor, reaction_type=reaction_type, initiative=self)

    def save(self, *args, **kwargs):
        if not self.link_preview:
            self.link_preview = LinkPreview.from_url(self.link)

        if self.link != self.link_preview.requested_url:
            self.link_preview = LinkPreview.from_url(self.link)

        super().save(*args, **kwargs)

    @classmethod
    def get_reactions_count(cls, initiative_id, reaction_type=None, reactor_id=None):
        reactions_query = Q(
            initiative_id=initiative_id,
        )

        if reaction_type:
            reactions_query.add(Q(reaction_type=reaction_type), Q.AND)

        if reactor_id:
            reactions_query.add(Q(reactor__id=reactor_id), Q.AND)

        return get_reactions(InitiativeReaction, reactions_query)


class InitiativeReaction(ModelWithUUID):
    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE, related_name="reactions")
    created = models.DateTimeField(editable=False)
    reactor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="initiative_reactions")
    reaction_type = models.CharField(max_length=20, choices=ReactionType.choices)

    class Meta:
        unique_together = (
            "reactor",
            "initiative",
        )

    @classmethod
    def create_reaction(cls, reactor: User, reaction_type: ReactionType, initiative: Initiative):
        InitiativeReaction.objects.filter(reactor=reactor, initiative=initiative).delete()
        return InitiativeReaction.objects.create(
            reactor=reactor, reaction_type=ReactionType.get_value(reaction_type), initiative=initiative
        )

    @classmethod
    def remove_reaction(cls, reactor: User, reaction_type: ReactionType, initiative: Initiative):
        return InitiativeReaction.objects.filter(
            reactor=reactor, reaction_type=ReactionType.get_value(reaction_type), initiative=initiative
        ).delete()

    @classmethod
    def count_reactions(
        cls, initiative_id: uuid.UUID, reactor_id: uuid.UUID = None, reaction_type: ReactionType = None
    ):
        count_query = Q(initiative_id=initiative_id, reactor__is_deleted=False)

        if reactor_id:
            count_query.add(Q(reactor_id=reactor_id), Q.AND)

        if reaction_type:
            count_query.add(Q(reaction_type=reaction_type), Q.AND)

        return cls.objects.filter(count_query).count()

    def save(self, *args, **kwargs):
        if not self.created:
            self.created = timezone.now()
        return super(InitiativeReaction, self).save(*args, **kwargs)
