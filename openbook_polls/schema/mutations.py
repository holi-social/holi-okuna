import strawberry
from asgiref.sync import sync_to_async
from strawberry.types import Info
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_polls.schema.types import CreatePollInput, Poll, Choice
from openbook_polls.models import Choice as ChoiceModel
from openbook_polls.models import Vote as VoteModel
from openbook_auth.utils import verify_authorized_user
from openbook_polls.serializers.poll_serializers import CreatePollSerializer
from openbook_common.helpers import to_input_dict
from django.db import transaction
from graphql import GraphQLError
import structlog
import uuid

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def create_poll(self, info: Info, input: CreatePollInput) -> Poll:
        current_user = verify_authorized_user(info)

        serializer = CreatePollSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.create_poll(**data)

    @strawberry.mutation
    @sync_to_async
    def update_votes(self, info: Info, id: uuid.UUID) -> Choice:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            choice = ChoiceModel.objects.get(id=id)

            poll = choice.poll

            if VoteModel.objects.filter(user=current_user, poll=poll).exists():
                raise GraphQLError(
                    f"User {current_user.username} has already voted for poll {poll.id}",
                    extensions={"code": GraphQLErrorCodes.BAD_USER_INPUT},
                )

            choice.increment_votes()
            VoteModel.objects.create(user=current_user, choice=choice, poll=poll)

            choice.refresh_from_db()

        return choice
