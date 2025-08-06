from typing import Any, TypeAlias

import strawberry
import strawberry_django
from strawberry.django.context import StrawberryDjangoContext

from ..models import (
    VolunteeringOpportunityStatus as VolunteeringOpportunityStatusModel,
    Status,
)

VolunteeringOpportunityStatusValue = strawberry.enum(Status, name="VolunteeringOpportunityStatusValue")


@strawberry_django.type(VolunteeringOpportunityStatusModel)
class VolunteeringOpportunityStatus:
    external_volunteering_opportunity_id: strawberry.auto
    status: VolunteeringOpportunityStatusValue


Info: TypeAlias = strawberry.Info[StrawberryDjangoContext, Any]
