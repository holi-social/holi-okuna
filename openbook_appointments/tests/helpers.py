from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema


def create_appointment(user, info):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CreateAppointmentInput!){
            createAppointment(input: $input) {
                id
                title
                inviteOnly
                participants {
                    fullName
                }
                startDateTime
                endDateTime
                location
                description
                permission
                videoCallLink {
                    url
                    additionalInfo
                }
                creator {
                    fullName
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": info},
    )
