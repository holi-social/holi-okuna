import uuid

import strawberry
import structlog
from asgiref.sync import sync_to_async

from favorites.models import UserFavorite as UserFavoriteModel
from favorites.schema.types import FavoritableType
from openbook_auth.utils import verify_authorized_user
from openbook_common.schema.types import Result

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def favorite(self, info, favoritable_id: uuid.UUID, favoritable_type: FavoritableType) -> Result:
        current_user = verify_authorized_user(info)
        UserFavoriteModel.favorite(user=current_user, favoritable_id=favoritable_id, favoritable_type=favoritable_type)
        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def unfavorite(self, info, favoritable_id: uuid.UUID, favoritable_type: FavoritableType) -> Result:
        current_user = verify_authorized_user(info)
        UserFavoriteModel.unfavorite(
            user=current_user, favoritable_id=favoritable_id, favoritable_type=favoritable_type
        )
        return Result(success=True)
