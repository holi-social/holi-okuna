from graphql import GraphQLError

from openbook_auth.models import UserBlock as UserBlockModel
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_polls.models import Question as QuestionModel


def resolve_poll(current_user, poll_id):
    try:
        # Check if post exists and user is not blocked => return 404 otherwise
        poll: QuestionModel = QuestionModel.objects.filter(QuestionModel.does_exist_query()).distinct().get(id=poll_id)
        UserBlockModel.filter_single_object(
            current_user,
            poll,
            lambda p: None if p.creator is None else p.creator.id,
        )
        try:
            # Check if post is visible => return 403 otherwise
            return QuestionModel.objects.filter(QuestionModel.is_visible_query(current_user)).distinct().get(id=poll_id)
        except QuestionModel.DoesNotExist:
            raise GraphQLError("Forbidden", extensions={"code": GraphQLErrorCodes.FORBIDDEN})
    except QuestionModel.DoesNotExist:
        raise GraphQLError("Poll not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
