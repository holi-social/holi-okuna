import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from openbook_auth.models import User, get_reactions
from openbook_common.enums import ReactionType
from openbook_common.models import ModelWithUUID, LinkPreview
from openbook_common.validators import url_safety_validator
from openbook_insights.models import Insight
from openbook_insights.models.external_content import ExternalContentCategory


class Quote(ModelWithUUID):
    insight = models.ForeignKey(Insight, on_delete=models.CASCADE, related_name="quotes")

    text = models.TextField(blank=False, null=False)

    author = models.CharField(max_length=255, blank=False, null=False)
    author_profession = models.CharField(max_length=255, blank=False, null=False)

    link = models.URLField(blank=False, null=False, validators=[url_safety_validator])
    link_preview = models.ForeignKey(LinkPreview, on_delete=models.SET_NULL, null=True)
    category = models.CharField(max_length=255, choices=ExternalContentCategory.choices)

    comment = models.TextField(blank=False, null=False, verbose_name="Why I recommend this content")

    def react(self, reactor, reaction_type):
        return QuoteReaction.create_reaction(reactor=reactor, reaction_type=reaction_type, quote=self)

    def clear_reaction(self, reactor, reaction_type):
        return QuoteReaction.remove_reaction(reactor=reactor, reaction_type=reaction_type, quote=self)

    def save(self, *args, **kwargs):
        if not self.link_preview:
            self.link_preview = LinkPreview.from_url(self.link)

        if self.link != self.link_preview.requested_url:
            self.link_preview = LinkPreview.from_url(self.link)

        super().save(*args, **kwargs)

    @classmethod
    def get_reactions_count(cls, quote_id, reaction_type=None, reactor_id=None):
        reactions_query = Q(
            quote_id=quote_id,
        )

        if reaction_type:
            reactions_query.add(Q(reaction_type=reaction_type), Q.AND)

        if reactor_id:
            reactions_query.add(Q(reactor__id=reactor_id), Q.AND)

        return get_reactions(QuoteReaction, reactions_query)


class QuoteReaction(ModelWithUUID):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="reactions")
    created = models.DateTimeField(editable=False)
    reactor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quote_reactions")
    reaction_type = models.CharField(max_length=20, choices=ReactionType.choices)

    class Meta:
        unique_together = (
            "reactor",
            "quote",
        )

    @classmethod
    def create_reaction(cls, reactor: User, reaction_type: ReactionType, quote: Quote):
        QuoteReaction.objects.filter(reactor=reactor, quote=quote).delete()
        return QuoteReaction.objects.create(reactor=reactor, reaction_type=reaction_type, quote=quote)

    @classmethod
    def remove_reaction(cls, reactor: User, reaction_type: ReactionType, quote: Quote):
        return QuoteReaction.objects.filter(reactor=reactor, reaction_type=reaction_type, quote=quote).delete()

    @classmethod
    def count_reactions(cls, quote_id: uuid.UUID, reactor_id: uuid.UUID = None, reaction_type: ReactionType = None):
        count_query = Q(quote_id=quote_id, reactor__is_deleted=False)

        if reactor_id:
            count_query.add(Q(reactor_id=reactor_id), Q.AND)

        if reaction_type:
            count_query.add(Q(reaction_type=reaction_type), Q.AND)

        return cls.objects.filter(count_query).count()

    def save(self, *args, **kwargs):
        if not self.created:
            self.created = timezone.now()
        return super(QuoteReaction, self).save(*args, **kwargs)
