import datetime
import uuid
from django.utils import timezone

import strawberry
import strawberry_django
from openbook_polls.models import Question as PollModel
from openbook_polls.models import Choice as ChoiceModel
from typing import Optional

@strawberry.input
class CreatePollInput:
    id: uuid.UUID
    question_text: str
    pub_date: timezone.now
    creator: uuid.UUID
    choice_text: str
    votes: Optional[int]

@strawberry_django.type(PollModel)
class Poll:
    id: strawberry.auto
    question_text: strawberry.auto
    pub_date: strawberry.auto
    creator: strawberry.auto
    choice_text: strawberry.auto
    votes: strawberry.auto

@strawberry_django.type(ChoiceModel)
class Choice:
    id: strawberry.auto
    choice_text: strawberry.auto
    votes: strawberry.auto
    question: Poll