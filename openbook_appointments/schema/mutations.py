import strawberry
import structlog
from asgiref.sync import sync_to_async

from openbook_appointments.schema.types import (
    Appointment,
    CreateAppointmentInput,
)
from openbook_appointments.serializers import CreateAppointmentSerializer
from openbook_appointments.services import AppointmentService
from openbook_auth.utils import verify_authorized_user
from openbook_common.helpers import to_input_dict

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def create_appointment(self, info, input: CreateAppointmentInput) -> Appointment:
        user = verify_authorized_user(info)

        serializer = CreateAppointmentSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return AppointmentService().create_appointment(
            space_id=data.get("space_id"),
            title=data.get("title"),
            invite_only=data.get("invite_only"),
            participant_ids=data.get("participant_ids"),
            start_date_time=data.get("start_date_time"),
            end_date_time=data.get("end_date_time"),
            location=data.get("location"),
            geolocation=data.get("geolocation"),
            description=data.get("description"),
            permission=data.get("permission"),
            thumbnail=data.get("thumbnail"),
            creator=user,
            video_call_link=data.get("video_call_link"),
            video_call_info=data.get("video_call_info"),
        )
