import uuid
from typing import Optional

from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema
from volunteering.models import Status


def list_committed_volunteering_opportunities(user, offset: int = 0, limit: int = 10):
    return async_to_sync(schema.execute)(
        """
            query($offset: Int!, $limit: Int!) {
                committedVolunteeringOpportunities(offset: $offset, limit: $limit) {
                    totalResults
                    data {
                        status
                        externalVolunteeringOpportunityId
                    }
                }
            }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"offset": offset, "limit": limit},
    )


def get_volunteering_opportunity_status(user, volunteering_opportunity_id: uuid.UUID):
    return async_to_sync(schema.execute)(
        """
            query($volunteeringOpportunityId: UUID!) {
                volunteeringOpportunityStatus(volunteeringOpportunityId: $volunteeringOpportunityId) {
                    status
                    externalVolunteeringOpportunityId
                }
            }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "volunteeringOpportunityId": str(volunteering_opportunity_id),
        },
    )


def update_volunteering_opportunity_status(
    user, volunteering_opportunity_id: uuid.UUID, new_status: Optional[Status] = None
):
    if new_status is None:
        return async_to_sync(schema.execute)(
            """
                mutation($volunteeringOpportunityId: UUID!) {
                    updateVolunteeringOpportunityStatus(volunteeringOpportunityId: $volunteeringOpportunityId) {
                        status
                        externalVolunteeringOpportunityId
                    }
                }
            """,
            context_value=benedict({"request": {"user": user}}),
            variable_values={
                "volunteeringOpportunityId": str(volunteering_opportunity_id),
            },
        )

    return async_to_sync(schema.execute)(
        """
            mutation($volunteeringOpportunityId: UUID!, $newStatus: VolunteeringOpportunityStatusValue) {
                updateVolunteeringOpportunityStatus(volunteeringOpportunityId: $volunteeringOpportunityId, newStatus: $newStatus) {
                    status
                    externalVolunteeringOpportunityId
                }
            }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "volunteeringOpportunityId": str(volunteering_opportunity_id),
            "newStatus": new_status.value,
        },
    )
