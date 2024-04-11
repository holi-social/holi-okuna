import datetime
import uuid
from django.utils import timezone

import strawberry
import strawberry_django
from openbook_polls.models import Question as PollModel
from openbook_polls.models import Choice as ChoiceModel
from typing import Optional
from typing import TYPE_CHECKING, Annotated, List, Optional, TypeVar

@strawberry.input
class CreatePollInput:
    #id: uuid.UUID
    question_text: str
    creator: uuid.UUID
    choices: List["CreateChoiceInput"]
    #votes: Optional[int]

@strawberry.input
class CreateChoiceInput:
    #id:uuid.UUID
    choice_text: str
    votes: int

@strawberry_django.type(PollModel)
class Poll:
    id: strawberry.auto
    question_text: strawberry.auto
    modified: strawberry.auto
    created: strawberry.auto
    creator: strawberry.auto
    is_public: strawberry.auto
    #choice_text: strawberry.auto
    #choice: List[Optional[Choice]]
    #votes: strawberry.auto

    @strawberry_django.field()
    def choices(self, info)-> List["Choice"]:
        return ChoiceModel.objects.filter(question=self)


@strawberry_django.type(ChoiceModel)
class Choice:
    id: strawberry.auto
    choice_text: strawberry.auto
    votes: strawberry.auto
    #question: Poll