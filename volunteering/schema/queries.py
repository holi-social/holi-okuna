import uuid
from typing import Optional, TYPE_CHECKING

import strawberry

from openbook_auth.utils import verify_authorized_user
from openbook_common.schema.types import Paged
from volunteering.models import VolunteeringOpportunityStatus as VolunteeringOpportunityStatusModel
from volunteering.schema.types import VolunteeringOpportunityStatus

if TYPE_CHECKING:
    from openbook_auth.models import User


@strawberry.type
class Query:
    @strawberry.field()
    async def volunteering_opportunity_status(
        self, info, volunteering_opportunity_id: uuid.UUID
    ) -> Optional[VolunteeringOpportunityStatus]:
        current_user: "User" = verify_authorized_user(info)

        return await VolunteeringOpportunityStatusModel.objects.filter(
            user=current_user, external_volunteering_opportunity_id=volunteering_opportunity_id
        ).afirst()

    @strawberry.field()
    async def committed_volunteering_opportunities(
        self, info, offset: int = 0, limit: int = 10
    ) -> Paged[VolunteeringOpportunityStatus]:
        current_user: "User" = verify_authorized_user(info)

        return await Paged.aof(VolunteeringOpportunityStatusModel.objects.filter(user=current_user), offset, limit)
