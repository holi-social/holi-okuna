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


class Choice(ModelWithUUID):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="polls")
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)

    def __str__(self):
        return self.choice_text
    



