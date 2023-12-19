import uuid

import strawberry
import strawberry_django

from openbook_appointments.enums import StatusType
from openbook_appointments.schema.types import Appointment
from openbook_appointments.services import AppointmentService
from openbook_common.schema.types import Paged


@strawberry.type
class Query:
    @strawberry_django.field()
    def appointments(
        self,
        info,
        space_id: uuid.UUID,
        status_type: StatusType = StatusType.UPCOMING,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[Appointment]:
        user = info.context.request.user

        return Paged.of(
            AppointmentService().get_appointments(
                user=user,
                space_id=space_id,
                status_type=status_type,
            ),
            offset,
            limit,
        )
