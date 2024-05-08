import strawberry
from asgiref.sync import sync_to_async
from strawberry.types import Info
from openbook_polls.schema.types import CreateQuestionInput, Question

from openbook_auth.utils import verify_authorized_user
from openbook_polls.serializers.poll_serializers import CreateQuestionSerializer
from openbook_common.helpers import to_input_dict


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def create_question(self, info: Info, input: CreateQuestionInput) -> Question:
        current_user = verify_authorized_user(info)

        serializer = CreateQuestionSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.create_question(**data)


# add mutation for votes + 1
