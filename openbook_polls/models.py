
from django.db import models
from openbook_auth.models import User
from django.utils import timezone

from openbook_common.models import (
    ModelWithUUID,
)

from openbook_common.utils.helpers import (
    get_magic,
)

from openbook_polls.checkers import (
    check_can_be_published,
)


from rest_framework.exceptions import ValidationError

from openbook_common.helpers import (
    PrefixedQ,
    attr_filled,
)

magic = get_magic()


class Question(ModelWithUUID):
    question_text = models.CharField(max_length=200)
    created = models.DateTimeField(editable=False, db_index=True)
    modified = models.DateTimeField(db_index=True, default=timezone.now)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="question", null=True)

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

    
    @classmethod
    def create_question(
        cls,
        creator, 
        question_text=None,
        created=None,
        is_draft=False,
        is_public=False,
    ) -> "Question":
        if not is_public:
            raise ValidationError("A poll requires to be public to be posted to.")

        question = Question.objects.create(creator=creator, created=created, question_text=question_text, is_public=is_public)

        if question_text:
            question.question_text=question_text
        
        if not is_draft:
            question.publish()
        else:
            question.save()
        
        return question


    def is_text_only_question(self):
        return self.has_text() 
    
    def has_text(self):
        return attr_filled(self, "text")
    
    def publish(self):
        check_can_be_published(question=self)
        self._publish()

    def _publish(self):
        self.status = Question.STATUS_PUBLISHED
        self.created = timezone.now()
        self.save()

    def is_draft(self):
        return self.status == Question.STATUS_DRAFT

    def is_empty(self):
        return not self.question_text

    def save(self, *args, **kwargs):
        """On create, update timestamps"""
        if not self.created:
            self.created = timezone.now()

        self.modified = timezone.now()
        
        super(Question, self).save(*args, **kwargs)

        return self

    def delete(self, *args, **kwargs):
        super(Question, self).delete(*args, **kwargs)
    
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
            (pQ(creator=user))
            | (pQ(status=Question.STATUS_PUBLISHED) & (pQ(is_public=True)))
        )


class Choice(ModelWithUUID):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="question")
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)

    def __str__(self):
        return self.choice_text
    



