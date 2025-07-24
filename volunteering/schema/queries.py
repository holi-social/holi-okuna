import uuid
from typing import TYPE_CHECKING

from django.apps import apps
import strawberry

from openbook_auth.utils import verify_authorized_user
from openbook_common.schema.types import Paged
from volunteering.schema.types import VolunteeringOpportunityStatus

if TYPE_CHECKING:
    from openbook_auth.models import User
    from volunteering.models import VolunteeringOpportunityStatus as VolunteeringOpportunityStatusModel


@strawberry.type
class Query:
    @strawberry.field()
    async def volunteering_opportunity_status(
        self, info, volunteering_opportunity_id: uuid.UUID
    ) -> VolunteeringOpportunityStatus:
        current_user: "User" = verify_authorized_user(info)
        Model: type["VolunteeringOpportunityStatusModel"] = apps.get_model(
            "volunteering.VolunteeringOpportunityStatus"
        )

        return await Model.objects.filter(
            user=current_user, external_volunteering_opportunity_id=volunteering_opportunity_id
        ).afirst()

    @strawberry.field()
    async def committed_volunteering_opportunities(
        self, info, offset: int = 0, limit: int = 10
    ) -> Paged[VolunteeringOpportunityStatus]:
        current_user: "User" = verify_authorized_user(info)
        Model: type["VolunteeringOpportunityStatusModel"] = apps.get_model(
            "volunteering.VolunteeringOpportunityStatus"
        )

        return await Paged.aof(Model.objects.filter(user=current_user), offset, limit)
