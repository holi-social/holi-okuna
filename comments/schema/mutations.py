import uuid
import strawberry
import structlog
from asgiref.sync import sync_to_async
from django.core.exceptions import PermissionDenied, FieldError
from django.db import transaction

from comments.enums import CommentableType
from comments.models import Comment as CommentModel
from comments.schema.serializers import CommentSerializer
from comments.schema.types.comment import Comment, CommentReactionInput, CreateCommentInput
from openbook_auth.utils import verify_authorized_user
from openbook_common.helpers import to_input_dict
from openbook_common.schema.types import Result

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
        parent_comment_id = data.get("parent_comment_id")

        with transaction.atomic():
            commentable = CommentModel.get_commentable(commentable_id, commentable_type)
            if parent_comment_id is not None:
                # only DISCUSSION type supports replying to comments
                if commentable_type is not CommentableType.DISCUSSION:
                    raise FieldError()

                parent_comment = CommentModel.objects.get(pk=parent_comment_id, commentable_id=commentable.id)
                comment = parent_comment.reply_to_comment(current_user, comment_text)
            else:
                comment = commentable.comment_on(current_user, comment_text)
        return comment

    @strawberry.mutation
    @sync_to_async
    def delete_comment(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        comment = CommentModel.objects.get(pk=id)
        comment.commentable.delete_comment(current_user, id)

        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def add_reaction_to_comment(
        self,
        info,
        input: CommentReactionInput,
    ) -> Comment:
        current_user = verify_authorized_user(info)
        comment = CommentModel.objects.get(pk=input.comment_id)

        if not comment.commentable.can_be_viewed(current_user):
            raise PermissionDenied()

        comment.react(current_user, input.reaction_type)
        return comment

    @strawberry.mutation
    @sync_to_async
    def remove_reaction_from_comment(
        self,
        info,
        input: CommentReactionInput,
    ) -> Comment:
        current_user = verify_authorized_user(info)
        comment = CommentModel.objects.get(pk=input.comment_id)

        if not comment.commentable.can_be_viewed(current_user):
            raise PermissionDenied()

        comment.clear_reaction(current_user, input.reaction_type)
        return comment
