from django.db import models
from openbook_auth.models import User
from django.utils import timezone
from django.db import transaction
from django.db.models import F


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


class Poll(ModelWithUUID):
    question_text = models.CharField(max_length=200)
    created = models.DateTimeField(editable=False, db_index=True)
    modified = models.DateTimeField(db_index=True, default=timezone.now)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="poll", null=True)

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
    def create_poll(
        cls,
        creator,
        question_text=None,
        created=None,
        is_draft=False,
        is_public=False,
    ) -> "Poll":
        if not is_public:
            raise ValidationError("A poll requires to be public to be posted to.")

        poll = Poll.objects.create(creator=creator, created=created, question_text=question_text, is_public=is_public)

        if question_text:
            poll.question_text = question_text

        if not is_draft:
            poll.publish()
        else:
            poll.save()

        return poll

    def is_text_only_poll(self):
        return self.has_text()

    def has_text(self):
        return attr_filled(self, "text")

    def publish(self):
        check_can_be_published(poll=self)
        self._publish()

    def _publish(self):
        self.status = Poll.STATUS_PUBLISHED
        self.created = timezone.now()
        self.save()

    def is_draft(self):
        return self.status == Poll.STATUS_DRAFT

    def is_empty(self):
        return not self.question_text

    def save(self, *args, **kwargs):
        """On create, update timestamps"""
        if not self.created:
            self.created = timezone.now()

        self.modified = timezone.now()

        super().save(*args, **kwargs)

        return self

    def delete(self, *args, **kwargs):
        super(Poll, self).delete(*args, **kwargs)

    @staticmethod
    def does_exist_query(prefix=None):
        pQ = PrefixedQ(prefix)

        return pQ(is_deleted=False)

    @staticmethod
    def is_visible_query(user, prefix=None):
        pQ = PrefixedQ(prefix)

        if user.is_anonymous:
            return pQ(is_deleted=False, status=Poll.STATUS_PUBLISHED, is_public=True)

        return pQ(is_deleted=False) & ((pQ(creator=user)) | (pQ(status=Poll.STATUS_PUBLISHED) & (pQ(is_public=True))))


class Choice(ModelWithUUID):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="poll")
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)

    def __str__(self):
        return self.choice_text

    @transaction.atomic
    def increment_votes(self):
        self.votes = F("votes") + 1
        self.save()


class Vote(ModelWithUUID):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    voting_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "poll")
