from typing import Any, TypeAlias

import strawberry
import strawberry_django
from strawberry.django.context import StrawberryDjangoContext

from ..models import (
    PetitionStatus as PetitionStatusModel,
    Status,
)

PetitionStatusValue = strawberry.enum(Status, name="PetitionStatusValue")


@strawberry_django.type(PetitionStatusModel)
class PetitionStatus:
    external_petition_id: strawberry.auto
    status: PetitionStatusValue


Info: TypeAlias = strawberry.Info[StrawberryDjangoContext, Any]
