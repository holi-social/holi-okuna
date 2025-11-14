from typing import Optional

from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema
from petitions.models import Status


def list_signed_petitions(user, offset: int = 0, limit: int = 10):
    return async_to_sync(schema.execute)(
        """
            query($offset: Int!, $limit: Int!) {
                signedPetitions(offset: $offset, limit: $limit) {
                    totalResults
                    data {
                        status
                        externalPetitionId
                    }
                }
            }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"offset": offset, "limit": limit},
    )


def get_petition_status(user, petition_id: str):
    return async_to_sync(schema.execute)(
        """
            query($petitionId: String!) {
                petitionStatus(petitionId: $petitionId) {
                    status
                    externalPetitionId
                }
            }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "petitionId": str(petition_id),
        },
    )


def update_petition_status(user, petition_id: str, new_status: Optional[Status] = None):
    if new_status is None:
        return async_to_sync(schema.execute)(
            """
                mutation($petitionId: String!) {
                    updatePetitionStatus(petitionId: $petitionId) {
                        status
                        externalPetitionId
                    }
                }
            """,
            context_value=benedict({"request": {"user": user}}),
            variable_values={
                "petitionId": str(petition_id),
            },
        )

    return async_to_sync(schema.execute)(
        """
            mutation($petitionId: String!, $newStatus: PetitionStatusValue) {
                updatePetitionStatus(petitionId: $petitionId, newStatus: $newStatus) {
                    status
                    externalPetitionId
                }
            }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "petitionId": str(petition_id),
            "newStatus": new_status.value,
        },
    )
