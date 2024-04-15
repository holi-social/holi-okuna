import strawberry
import structlog
from asgiref.sync import sync_to_async

from openbook_auth.utils import verify_authorized_user
from openbook_common.helpers import to_input_dict
from feed_posts.schema.types import FeedPost, CreateFeedPostInput
from feed_posts.serializers import CreateFeedPostSerializer
from feed_posts.services import FeedPostService

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
            creator=user,
        )
