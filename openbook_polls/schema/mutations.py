from typing import List

import strawberry
from asgiref.sync import sync_to_async
from strawberry.types import Info
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.schema.types import Result
from openbook_polls.schema.types import CreatePollInput, Poll, Choice
from openbook_polls.models import Choice as ChoiceModel, Vote as VoteModel, Poll as PollModel
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

    @strawberry.mutation(deprecation_reason="Use vote_on_poll instead.")
    @sync_to_async
    def update_votes(self, info: Info, id: uuid.UUID) -> Choice:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            choice = ChoiceModel.objects.get(id=id)

            poll = choice.poll

            if VoteModel.objects.filter(user=current_user, choice__poll=poll).exists():
                raise GraphQLError(
                    f"User {current_user.username} has already voted for poll {poll.id}",
                    extensions={"code": GraphQLErrorCodes.BAD_USER_INPUT},
                )

            choice.increment_votes()
            VoteModel.objects.create(user=current_user, choice__poll=poll)

            choice.refresh_from_db()

        return choice

    @strawberry.mutation
    @sync_to_async
    def vote_on_poll(self, info: Info, poll_id: uuid.UUID, choice_ids: List[uuid.UUID]) -> Result:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            try:
                poll = PollModel.objects.get(id=poll_id)
            except PollModel.DoesNotExist as err:
                raise GraphQLError(
                    f"Poll {poll_id} not found.",
                    extensions={"code": GraphQLErrorCodes.NOT_FOUND},
                ) from err

            if not poll.is_multi_select and len(choice_ids) > 1:
                raise GraphQLError(
                    f"Poll {poll.id} does not allow multiple choices.",
                    extensions={"code": GraphQLErrorCodes.BAD_USER_INPUT},
                )

            if poll.max_choices and len(choice_ids) > poll.max_choices:
                raise GraphQLError(
                    f"Poll {poll.id} allows a maximum of {poll.max_choices} choices.",
                    extensions={"code": GraphQLErrorCodes.BAD_USER_INPUT},
                )

            existing_votes = VoteModel.objects.filter(user=current_user, choice__poll=poll)

            if existing_votes.exists():
                raise GraphQLError(
                    f"User {current_user.username} has already voted in poll {poll.id}.",
                    extensions={"code": GraphQLErrorCodes.BAD_USER_INPUT},
                )

            choices = list(ChoiceModel.objects.filter(id__in=choice_ids))

            if len(choices) != len(choice_ids):
                raise GraphQLError(
                    "One or more choices are invalid.",
                    extensions={"code": GraphQLErrorCodes.BAD_USER_INPUT},
                )

            if any(choice.poll_id != poll_id for choice in choices):
                raise GraphQLError(
                    "All selected choices must belong to the same poll.",
                    extensions={"code": GraphQLErrorCodes.BAD_USER_INPUT},
                )

            for choice in choices:
                choice.increment_votes()
                VoteModel.objects.create(user=current_user, choice=choice)

        return Result(success=True)
