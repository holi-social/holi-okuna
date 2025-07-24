import strawberry
import strawberry_django

from ..models import (
    VolunteeringOpportunityStatus as VolunteeringOpportunityStatusModel,
    Status,
)

VolunteeringOpportunityStatusValue = strawberry.enum(Status, name="VolunteeringOpportunityStatusValue")


@strawberry_django.type(VolunteeringOpportunityStatusModel)
class VolunteeringOpportunityStatus:
    external_volunteering_opportunity_id: strawberry.auto
    status: VolunteeringOpportunityStatusValue
