types.py
import datetime
import uuid
import strawberry
import strawberry_django
from django.db.models import Q
from openbook_polls.models import Question as PollModel
from openbook_polls.models import Choice as ChoiceModel
@strawberry.input
class CreatePollInput:
    id: uuid.UUID
    question_text: str
    pub_date: datetime.datetime
    creator_id: uuid.UUID
    choice_text: str
    votes: int
@strawberry_django.type(PollModel)
class Poll:
    id: strawberry.auto
    question_text: strawberry.auto
    pub_date: strawberry.auto
    creator_id: strawberry.auto
@strawberry_django.type(ChoiceModel)
class Choice:
    id: strawberry.auto
    choice_text: strawberry.auto
    votes: strawberry.auto
    question: Poll







