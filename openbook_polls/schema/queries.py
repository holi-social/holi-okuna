import uuid
from typing import Optional

import strawberry
import strawberry_django

from openbook_polls.schema.types import Poll
from openbook_polls.schema.utils import resolve_poll


@strawberry.type
class Query:
    @strawberry_django.field()
    def poll_by_id(self, info, id: uuid.UUID) -> Optional[Poll]:
        return resolve_poll(info.context.request.user, id)
