import uuid

import strawberry
import structlog
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist

from favorites.models import UserFavorite as UserFavoriteModel
from favorites.schema.types import FavoritableType
from openbook_auth.utils import verify_authorized_user
from openbook_common.schema.types import Result
from openbook_common.utils.helpers import is_uuid

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation(
        deprecation_reason="use newer api with string favoritable ids to favorite all the things, keep for <=1.57.1"
    )
    @sync_to_async
    def favorite(self, info, favoritable_id: uuid.UUID, favoritable_type: FavoritableType) -> Result:
        current_user = verify_authorized_user(info)
        UserFavoriteModel.favorite(user=current_user, favoritable_id=favoritable_id, favoritable_type=favoritable_type)
        return Result(success=True)

    @strawberry.mutation(
        deprecation_reason="use newer api with string favoritable ids to favorite all the things, keep for <=1.57.1"
    )
    @sync_to_async
    def unfavorite(self, info, favoritable_id: uuid.UUID, favoritable_type: FavoritableType) -> Result:
        current_user = verify_authorized_user(info)
        UserFavoriteModel.unfavorite(
            user=current_user, favoritable_id=favoritable_id, favoritable_type=favoritable_type
        )
        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def favorite_v2(self, info, favoritable_id: str, favoritable_type: FavoritableType) -> Result:
        current_user = verify_authorized_user(info)

        if FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY != favoritable_type:
            if not is_uuid(favoritable_id):
                return Result(success=False)

        try:
            UserFavoriteModel.favorite(
                user=current_user, favoritable_id=favoritable_id, favoritable_type=favoritable_type
            )
            return Result(success=True)
        except ObjectDoesNotExist:
            logger.error(
                f"Favoritable object {favoritable_id} of type {favoritable_type} does not exist or isn't accessible"
            )
            return Result(success=False)

    @strawberry.mutation
    @sync_to_async
    def unfavorite_v2(self, info, favoritable_id: str, favoritable_type: FavoritableType) -> Result:
        current_user = verify_authorized_user(info)
        UserFavoriteModel.unfavorite(
            user=current_user, favoritable_id=favoritable_id, favoritable_type=favoritable_type
        )
        return Result(success=True)
