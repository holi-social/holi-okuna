import uuid
from typing import Annotated, TYPE_CHECKING

from django.apps import apps
import strawberry

from openbook_auth.utils import verify_authorized_user
from volunteering.schema.types import VolunteeringOpportunityStatus

if TYPE_CHECKING:
    from openbook_auth.models import User


@strawberry.type
class Query:
    @strawberry.field()
    def volunteering_opportunity_status(
        self, info, volunteering_opportunity_id: Annotated[uuid.UUID, strawberry.argument()]
    ) -> VolunteeringOpportunityStatus:
        current_user: "User" = verify_authorized_user(info)
        Model = apps.get_model("volunteering.VolunteeringOpportunityStatus")

        return Model.objects.filter(
            user__id=current_user.id, external_volunteering_opportunity_id=volunteering_opportunity_id
        ).first()
