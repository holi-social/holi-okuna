import datetime
from datetime import timedelta

from django.db import models
from openbook_auth.models import User
from django.utils import timezone

from openbook_common.models import (
    ModelWithUUID,
    OrderedModelWithUUID,
)

from openbook_common.helpers import (
    PQ,
    ExifRotate,
    PrefixedQ,
)



class Question(ModelWithUUID):
    question_text = models.CharField(max_length=200)
    #pub_date = models.DateTimeField("date published")
    created = models.DateTimeField(editable=False, db_index=True)
    modified = models.DateTimeField(db_index=True, default=timezone.now)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="polls", null=True)

    is_edited = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    STATUS_DRAFT = "D"
    STATUS_PROCESSING = "PG"
    STATUS_PUBLISHED = "P"
    STATUSES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PUBLISHED, "Published"),
    )
    status = models.CharField(blank=False, null=False, choices=STATUSES, default=STATUS_DRAFT, max_length=2)

    is_public = models.BooleanField(default=False, db_index=True)


    def save(self, *args, **kwargs):
        """On create, update timestamps"""
        if not self.created:
            self.created = timezone.now()

        self.modified = timezone.now()

        poll = super(Question, self).save(*args, **kwargs)

        return self
    
    @classmethod
    def create_question(
        creator, 
        created=None,
        question_text=None,
        choice_text=None,
        votes=None
        ) -> "Question":

        poll = Question.objects.create(creator=creator, created=created, question_text=question_text)

        if question_text:
            poll.question_text=question_text
        
        if choice_text:
            poll.choice_text=choice_text

        if votes:
            poll.votes=votes
        
        poll.save()
        
        return poll
    
    @staticmethod
    def does_exist_query(prefix=None):
        pQ = PrefixedQ(prefix)

        return pQ(is_deleted=False)
    
    @staticmethod
    def is_visible_query(user, prefix=None):
        pQ = PrefixedQ(prefix)

        if user.is_anonymous:
            return pQ(is_deleted=False, status=Question.STATUS_PUBLISHED, is_public=True)

        return pQ(is_deleted=False) & (
            (pQ(creator=user) & (pQ(community__isnull=True) | pQ(community__memberships__user__id=user.id)))
            | (pQ(status=Question.STATUS_PUBLISHED) & (pQ(is_public=True) | pQ(community__memberships__user__id=user.id)))
        )


class Choice(ModelWithUUID):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="polls")
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)

    def __str__(self):
        return self.choice_text
    



