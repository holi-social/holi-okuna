import uuid
from typing import Optional
from openbook_auth.utils import verify_authorized_user
from openbook_polls.models import Poll as PollModel
from openbook_polls.models import Vote as VoteModel

import strawberry
import strawberry_django

from openbook_polls.schema.types import Poll
from openbook_polls.schema.utils import resolve_poll


@strawberry.type
class Query:
    @strawberry_django.field()
    def poll_by_id(self, info, id: uuid.UUID) -> Optional[Poll]:
        return resolve_poll(info.context.request.user, id)

    @strawberry_django.field()
    def user_has_voted_by_poll_id(self, info, id: uuid.UUID) -> bool:
        current_user = verify_authorized_user(info)
        poll = PollModel.objects.get(id=id)

        return VoteModel.objects.filter(user=current_user, choice__poll=poll).exists()
