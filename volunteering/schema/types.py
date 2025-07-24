import strawberry
import strawberry_django

from ..models import (
    VolunteeringOpportunityStatus as VolunteeringOpportunityStatusModel,
    Status,
)


@strawberry_django.type(VolunteeringOpportunityStatusModel)
class VolunteeringOpportunityStatus:
    external_volunteering_opportunity_id: strawberry.auto
    status: Status
