import datetime

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
    pub_date = models.DateTimeField("date published")
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="polls", null=True)

    def __str__(self):
        return self.question_text

    def was_published_recently(self):
        return self.pub_date >= timezone.now() - datetime.timedelta(days=1)
    
    @staticmethod
    def does_exist_query(prefix=None):
        pQ = PrefixedQ(prefix)

        return pQ(is_deleted=False)

    @staticmethod
    def is_visible_query(user, prefix=None):
        pQ = PrefixedQ(prefix)

        if user.is_anonymous:
            return pQ(is_deleted=False, status=Post.STATUS_PUBLISHED, is_public=True)

        return pQ(is_deleted=False) & (
            (pQ(creator=user) & (pQ(community__isnull=True) | pQ(community__memberships__user__id=user.id)))
            | (pQ(status=Post.STATUS_PUBLISHED) & (pQ(is_public=True) | pQ(community__memberships__user__id=user.id)))
        )


class Choice(ModelWithUUID):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="polls")
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)

    def __str__(self):
        return self.choice_text
    



