import typing

import strawberry
from graphql import GraphQLError

from openbook.graphql_errors import GraphQLErrorCodes
from openbook_auth.utils import verify_authorized_user
from petitions.models import PetitionStatus as PetitionStatusModel, Status
from petitions.schema.types import PetitionStatus, PetitionStatusValue, Info

if typing.TYPE_CHECKING:
    from openbook_auth.models import User


@strawberry.type
class Mutation:
    @strawberry.mutation()
    async def update_petition_status(
        self,
        info: Info,
        petition_id: str,
        new_status: PetitionStatusValue = PetitionStatusValue.PLANNED,
    ) -> PetitionStatus:
        user: "User" = verify_authorized_user(info)
        record = await PetitionStatusModel.objects.filter(user=user, external_petition_id=petition_id).afirst()

        if record is None:
            record = PetitionStatusModel(
                user=user,
                external_petition_id=petition_id,
                status=PetitionStatusValue.PLANNED.value,
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
