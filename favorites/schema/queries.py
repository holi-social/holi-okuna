import strawberry
import strawberry_django
import structlog
from django.contrib.contenttypes.models import ContentType as ContentTypeModel
from django.core.exceptions import ObjectDoesNotExist

from favorites.models import UserFavorite as UserFavoriteModel
from favorites.schema.types import UserFavorite, FavoritableType
from openbook_auth.utils import verify_authorized_user
from openbook_common.schema.types import Paged

logger = structlog.get_logger(__name__)


@strawberry.type
class Query:
    @strawberry_django.field()
    def favorites(self, info, offset: int = 0, limit: int = 10) -> Paged[UserFavorite]:
        current_user = verify_authorized_user(info)
        favorites = UserFavoriteModel.objects.filter(user=current_user).order_by("-created_at")
        return Paged.of(favorites, offset, limit)

    @strawberry_django.field()
    def favorites_by_type(
        self, info, favoritable_type: FavoritableType, offset: int = 0, limit: int = 10
    ) -> Paged[UserFavorite]:
        current_user = verify_authorized_user(info)
        content_type_model = ContentTypeModel.objects.filter(model=favoritable_type.value).first()
        favorites_of_type = UserFavoriteModel.objects.filter(
            user=current_user, favoritable_type=content_type_model.id
        ).order_by("-created_at")
        return Paged.of(favorites_of_type, offset, limit)

    @strawberry_django.field()
    def favorite(self, info, favoritable_id: str) -> UserFavorite:
        current_user = verify_authorized_user(info)
        favorite = (
            UserFavoriteModel.objects.filter(user=current_user, favoritable_id=favoritable_id)
            .order_by("-created_at")
            .first()
        )

        if favorite is None:
            raise ObjectDoesNotExist
        else:
            return favorite
