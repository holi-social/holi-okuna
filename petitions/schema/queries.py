from typing import Optional, TYPE_CHECKING

import strawberry

from openbook_auth.utils import verify_authorized_user
from openbook_common.schema.types import Paged
from petitions.models import PetitionStatus as PetitionStatusModel
from petitions.schema.types import PetitionStatus, Info

if TYPE_CHECKING:
    from openbook_auth.models import User


@strawberry.type
class Query:
    @strawberry.field()
    async def petition_status(self, info: Info, petition_id: str) -> Optional[PetitionStatus]:
        current_user: "User" = verify_authorized_user(info)

        return await PetitionStatusModel.objects.filter(user=current_user, external_petition_id=petition_id).afirst()

    @strawberry.field()
    async def signed_petitions(self, info: Info, offset: int = 0, limit: int = 10) -> Paged[PetitionStatus]:
        current_user: "User" = verify_authorized_user(info)

        return await Paged.aof(
            PetitionStatusModel.objects.filter(user=current_user).order_by("-updated_at"), offset, limit
        )
