import strawberry
import strawberry_django
import structlog

from favorites.models import UserFavorite as UserFavoriteModel, UserFavorite
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
