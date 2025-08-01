import typing

import strawberry
from graphql import GraphQLError

from openbook.graphql_errors import GraphQLErrorCodes
from openbook_auth.utils import verify_authorized_user
from volunteering.models import VolunteeringOpportunityStatus as VolunteeringOpportunityStatusModel, Status
from volunteering.schema.types import VolunteeringOpportunityStatus, VolunteeringOpportunityStatusValue, Info

if typing.TYPE_CHECKING:
    from openbook_auth.models import User


@strawberry.type
class Mutation:
    @strawberry.mutation()
    async def update_volunteering_opportunity_status(
        self,
        info: Info,
        volunteering_opportunity_id: str,
        new_status: VolunteeringOpportunityStatusValue = VolunteeringOpportunityStatusValue.TO_DO,
    ) -> VolunteeringOpportunityStatus:
        user: "User" = verify_authorized_user(info)
        record = await VolunteeringOpportunityStatusModel.objects.filter(
            user=user, external_volunteering_opportunity_id=volunteering_opportunity_id
        ).afirst()

        if record is None:
            record = VolunteeringOpportunityStatusModel(
                user=user,
                external_volunteering_opportunity_id=volunteering_opportunity_id,
                status=VolunteeringOpportunityStatusValue.TO_DO.value,
            )
            await record.asave()
            return record

        if record.status == new_status.value:
            return record

        if not Status.is_transition_allowed(Status(record.status), new_status):
            raise GraphQLError(
                "Transition to this status is not allowed",
                extensions={
                    "code": GraphQLErrorCodes.BAD_USER_INPUT,
                },
            )

        record.status = new_status.value
        await record.asave()

        return record
