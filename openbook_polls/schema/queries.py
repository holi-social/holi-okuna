import uuid
from typing import Optional

import strawberry
import strawberry_django

from openbook_polls.schema.types import Question
from openbook_polls.schema.utils import resolve_question


@strawberry.type
class Query:
    @strawberry_django.field()
    def poll_by_id(self, info, id: uuid.UUID) -> Optional[Question]:
        return resolve_question(info.context.request.user, id)
