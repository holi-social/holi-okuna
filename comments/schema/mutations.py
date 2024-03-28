import strawberry
import structlog
from asgiref.sync import sync_to_async
from django.db import transaction

from comments.schema.serializers import CommentSerializer
from comments.schema.types.comment import Comment, CreateCommentInput
from openbook_auth.utils import verify_authorized_user
from openbook_common.helpers import to_input_dict

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def add_comment(self, info, input: CreateCommentInput) -> Comment:
        current_user = verify_authorized_user(info)

        serializer = CommentSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comment_text = data.get("text")
        ##commentable_type = data.get("commentable_type")
        commentable_id = data.get("commentable_id")

        with transaction.atomic():
            comment = current_user.comment_post_with_id(post_id=commentable_id, text=comment_text)

        return comment
