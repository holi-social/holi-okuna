import uuid
from typing import Optional

import strawberry
import strawberry_django

from openbook_common.schema.types import Paged
from openbook_polls.schema.types import Poll
from openbook_polls.schema.utils import resolve_poll
from openbook_polls.models import  Question as QuestionModel
from openbook_auth.models import User as UserModel


@strawberry.type
class Query:
    @strawberry_django.field()
    def poll_by_id(self, info, id: uuid.UUID) -> Optional[Poll]:
        return resolve_post(info.context.request.user, id)

    @strawberry_django.field()
    def inspiration_poll(self, info, offset: int = 0, limit: int = 10) -> Paged[Poll]:
        current_user: UserModel = info.context.request.user
        query = QuestionModel.objects.filter(
            QuestionModel.is_visible_query(current_user),
        ).distinct()
        return Paged.of(query.order_by("-created"), offset, limit)
