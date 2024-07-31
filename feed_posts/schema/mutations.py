import uuid

import strawberry
import structlog
from asgiref.sync import sync_to_async

from openbook_auth.utils import verify_authorized_user
from openbook_common.enums import ReactionType, ReactionAction
from openbook_common.helpers import to_input_dict, is_parameter_null
from feed_posts.models import FeedPost as FeedPostModel
from feed_posts.schema.types import FeedPost, CreateFeedPostInput, UpdateFeedPostInput
from feed_posts.serializers import CreateFeedPostSerializer, UpdateFeedPostSerializer
from feed_posts.services import FeedPostService, FeedPostReactionService
from openbook_common.schema.types import Result

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def create_feed_post(self, info, input: CreateFeedPostInput) -> FeedPost:
        user = verify_authorized_user(info)

        serializer = CreateFeedPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return FeedPostService().create_feed_post(
            title=data.get("title"),
            visibility=data.get("visibility"),
            description=data.get("description"),
            category_id=data.get("category_id"),
            topic_ids=data.get("topic_ids"),
            image=data.get("image"),
            creator=user,
            language=data.get("language"),
        )

    @strawberry.mutation
    @sync_to_async
    def update_feed_post(self, info, input: UpdateFeedPostInput) -> FeedPost:
        user = verify_authorized_user(info)

        serializer = UpdateFeedPostSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        return FeedPostService().update_feed_post(
            user=user,
            post_id=data.get("post_id"),
            title=data.get("title"),
            visibility=data.get("visibility"),
            description=data.get("description"),
            category_id=data.get("category_id"),
            topic_ids=data.get("topic_ids"),
            image=data.get("image"),
            remove_image=is_parameter_null(data, "image"),
            language=data.get("language"),
        )

    @strawberry.mutation
    @sync_to_async
    def delete_feed_post(self, info, post_id: uuid.UUID) -> Result:
        user = verify_authorized_user(info)

        FeedPostService().delete_feed_post(user=user, post_id=post_id)

        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def update_feed_post_reaction(
        self,
        info,
        post_id: uuid.UUID,
        reaction_type: ReactionType,
        reaction_action: ReactionAction,
    ) -> FeedPost:
        current_user = verify_authorized_user(info)
        feed_post = FeedPostModel.objects.get(id=post_id)

        if reaction_action == ReactionAction.SET:
            FeedPostReactionService().create_reaction(
                feed_post=feed_post, reactor=current_user, reaction_type=reaction_type
            )
        else:
            FeedPostReactionService().remove_reaction(
                feed_post=feed_post, reactor=current_user, reaction_type=reaction_type
            )
        return feed_post
