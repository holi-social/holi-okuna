import uuid

import strawberry
import strawberry_django
from openbook_polls.models import Poll as PollModel
from openbook_polls.models import Choice as ChoiceModel
from openbook_auth.schema.types import User
from typing import List, Optional


@strawberry.input
class CreatePollInput:
    question_text: str


@strawberry.input
class CreateChoiceInput:
    poll_id: uuid.UUID
    choice_text: str


@strawberry.input
class UpdatePollInput:
    poll_id: uuid.UUID
    question_text: Optional[str] = strawberry.UNSET


@strawberry_django.type(PollModel)
class Poll:
    id: strawberry.auto
    question_text: strawberry.auto
    modified: strawberry.auto
    created: strawberry.auto
    creator: strawberry.auto
    creator: User = strawberry_django.field(select_related="creator__profile")
    is_public: strawberry.auto

    @strawberry_django.field()
    def choices(self, info) -> List["Choice"]:
        return ChoiceModel.objects.filter(poll=self)


@strawberry_django.type(ChoiceModel)
class Choice:
    id: strawberry.auto
    choice_text: strawberry.auto
    votes: strawberry.auto
