import strawberry
import structlog
from asgiref.sync import sync_to_async
from django.db import transaction

from comments.models import Comment as CommentModel
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
        commentable_type = data.get("commentable_type")
        commentable_id = data.get("commentable_id")

        with transaction.atomic():
            commentable = CommentModel.get_commentable(commentable_type, commentable_id)
            comment = commentable.comment_on(text=comment_text, commenter=current_user)

        return comment
