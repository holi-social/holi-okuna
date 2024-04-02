import uuid

import strawberry
import structlog
from asgiref.sync import sync_to_async

from favorites.models import UserFavorite
from openbook_auth.schema.types import BookmarkType
from openbook_auth.utils import verify_authorized_user
from openbook_common.schema.types import Result

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def bookmark(self, info, bookmark_id: uuid.UUID, bookmark_type: BookmarkType) -> Result:
        current_user = verify_authorized_user(info)
        UserFavorite.bookmark(user=current_user, bookmark_id=bookmark_id, bookmark_type=bookmark_type)
        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def unbookmark(self, info, bookmark_id: uuid.UUID, bookmark_type: BookmarkType) -> Result:
        current_user = verify_authorized_user(info)
        UserFavorite.unbookmark(user=current_user, bookmark_id=bookmark_id, bookmark_type=bookmark_type)
        return Result(success=True)
