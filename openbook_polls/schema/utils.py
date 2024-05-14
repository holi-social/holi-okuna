from graphql import GraphQLError

from openbook_auth.models import UserBlock as UserBlockModel
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_polls.models import Poll as PollModel


def resolve_poll(current_user, poll_id):
    try:
        # Check if poll exists and user is not blocked => return 404 otherwise
        poll: PollModel = PollModel.objects.filter(PollModel.does_exist_query()).get(id=poll_id)
        UserBlockModel.filter_single_object(
            current_user,
            poll,
            lambda p: None if p.creator is None else p.creator.id,
        )
        try:
            # Check if poll is visible => return 403 otherwise
            return PollModel.objects.filter(PollModel.is_visible_query(current_user)).get(id=poll_id)
        except PollModel.DoesNotExist:
            raise GraphQLError("Forbidden", extensions={"code": GraphQLErrorCodes.FORBIDDEN}) from None
    except PollModel.DoesNotExist:
        raise GraphQLError("Poll not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND}) from None
