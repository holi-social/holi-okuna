import uuid

import strawberry
import structlog
from asgiref.sync import sync_to_async
from django.db import transaction
from strawberry.types import Info

from comments.models import Comment as CommentModel
from openbook_auth.utils import verify_authorized_user
from openbook_common.enums import ReactionAction, ReactionType
from openbook_common.helpers import is_parameter_null, to_input_dict
from openbook_common.schema.types import Result
from openbook_communities.models import Community as CommunityModel
from openbook_communities.schema.types import Space
from openbook_posts.models import Post as PostModel
from openbook_posts.schema.types import (
    CreatePostCommentInput,
    CreatePostCommentOutput,
    CreatePostInput,
    Post,
    PostComment,
    UpdatePostInput,
)
from openbook_posts.schema.utils import resolve_post
from openbook_posts.serializers.post_comments_serializers import CommentPostSerializer
from openbook_posts.serializers.post_serializers import EditCommunityPostSerializer
from openbook_posts.serializers.posts_serializers import CreateCommunityPostSerializer

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation(deprecation_reason="Comments can be added to other objects. Use updateComment mutation.")
    @sync_to_async
    def update_post_comment(self, info, input: CreatePostCommentInput) -> CreatePostCommentOutput:
        current_user = verify_authorized_user(info)

        serializer = CommentPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comment_text = data.get("text")
        post_id = data.get("post_id")
        language = data.get("language")

        with transaction.atomic():
            post_comment = current_user.comment_post_with_id(post_id=post_id, text=comment_text,language=language)

        return CreatePostCommentOutput(post_comment=post_comment, post_by_id=resolve_post(current_user, post_id))

    @strawberry.mutation(deprecation_reason="Comments can be deleted from other objects. Use deleteComment mutation.")
    @sync_to_async
    def delete_post_comment(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        current_user.delete_comment_with_id(post_comment_id=id)

        return Result(success=True)

    @strawberry.mutation(
        deprecation_reason="Changed return type to reflect created entity, use create_space_post_2. Deprecated since v1.1.0"
    )
    @sync_to_async
    def create_space_post(self, info: Info, input: CreatePostInput) -> Space:
        current_user = verify_authorized_user(info)

        serializer = CreateCommunityPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        current_user.create_community_post(**data)

        return CommunityModel.objects.get(id=data.get("space_id"))

    @strawberry.mutation
    @sync_to_async
    def create_space_post_2(self, info: Info, input: CreatePostInput) -> Post:
        current_user = verify_authorized_user(info)

        serializer = CreateCommunityPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.create_community_post(**data)

    @strawberry.mutation
    @sync_to_async
    def update_space_post(self, info: Info, input: UpdatePostInput) -> Post:
        current_user = verify_authorized_user(info)

        serializer = EditCommunityPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        data["remove_image"] = is_parameter_null(data, "image")

        return current_user.update_community_post(**data)

    @strawberry.mutation
    @sync_to_async
    def delete_space_post(self, info: Info, id: uuid.UUID) -> Space:
        current_user = verify_authorized_user(info)

        post = PostModel.objects.get(id=id)
        current_user.delete_post(post)

        return post.community

    @strawberry.mutation
    @sync_to_async
    def update_post_reaction(
        self,
        info,
        id: uuid.UUID,
        reaction_type: ReactionType,
        reaction_action: ReactionAction,
    ) -> Post:
        current_user = verify_authorized_user(info)
        post = PostModel.objects.get(id=id)
        if reaction_action == ReactionAction.SET:
            post.react(current_user, reaction_type)
        else:
            post.clear_reaction(current_user, reaction_type)
        return post

    @strawberry.mutation(
        deprecation_reason="Comment reactions can be added to other objects. Use updateCommentReaction mutation."
    )
    @sync_to_async
    def update_post_comment_reaction(
        self,
        info,
        id: uuid.UUID,
        reaction_type: ReactionType,
        reaction_action: ReactionAction,
    ) -> PostComment:
        current_user = verify_authorized_user(info)
        post_comment = CommentModel.objects.get(id=id)
        if reaction_action == ReactionAction.SET:
            post_comment.react(current_user, reaction_type)
        else:
            post_comment.clear_reaction(current_user, reaction_type)
        return post_comment
