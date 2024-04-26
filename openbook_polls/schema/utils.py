from graphql import GraphQLError

from openbook_auth.models import UserBlock as UserBlockModel
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_polls.models import Question as QuestionModel


def resolve_question(current_user, question_id):
    try:
        # Check if poll exists and user is not blocked => return 404 otherwise
        question: QuestionModel = QuestionModel.objects.filter(QuestionModel.does_exist_query()).distinct().get(id=question_id)
        UserBlockModel.filter_single_object(
            current_user,
            question,
            lambda p: None if p.creator is None else p.creator.id,
        )
        try:
            # Check if poll is visible => return 403 otherwise
            return QuestionModel.objects.filter(QuestionModel.is_visible_query(current_user)).distinct().get(id=question_id)
        except QuestionModel.DoesNotExist:
            raise GraphQLError("Forbidden", extensions={"code": GraphQLErrorCodes.FORBIDDEN})
    except QuestionModel.DoesNotExist:
        raise GraphQLError("Question not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
