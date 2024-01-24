from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema
from openbook_appointments.enums import StatusType


def create_appointment(user, input):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CreateAppointmentInput!){
            createAppointment(input: $input) {
                id
                title
                slug
                inviteOnly
                participants {
                    fullName
                }
                startDateTime
                endDateTime
                locationDetails {
                    completeAddress
                    city
                    state
                    country
                    geolocation {
                        latitude
                        longitude
                    }
                }
                description
                permission
                videoCallLink {
                    url
                    additionalInfo
                }
                creator {
                    fullName
                }
                isHybrid
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": input},
    )


def update_appointment(user, input):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: UpdateAppointmentInput!){
            updateAppointment(input: $input) {
                id
                title
                slug
                inviteOnly
                participants {
                    fullName
                }
                startDateTime
                endDateTime
                locationDetails {
                    completeAddress
                    city
                    state
                    country
                    geolocation {
                        latitude
                        longitude
                    }
                }
                description
                permission
                videoCallLink {
                    url
                    additionalInfo
                }
                creator {
                    fullName
                }
                isHybrid
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": input},
    )


def appointments(user, space_id, status_type: StatusType):
    return async_to_sync(schema.execute)(
        """
        query($spaceId: UUID!, $statusType: StatusType!){
            appointments(spaceId: $spaceId, statusType: $statusType) {
                totalResults
                data {
                    id
                    title
                    slug
                    inviteOnly
                    participants {
                        fullName
                    }
                    startDateTime
                    endDateTime
                    locationDetails {
                        completeAddress
                        city
                        state
                        country
                        geolocation {
                            latitude
                            longitude
                        }
                    }
                    description
                    permission
                    videoCallLink {
                        url
                        additionalInfo
                    }
                    creator {
                        fullName
                    }
                    isHybrid
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "spaceId": str(space_id),
            "statusType": status_type.value,
        },
    )


def appointment(user, id_or_slug):
    return async_to_sync(schema.execute)(
        """
        query($idOrSlug: String!){
            appointment(idOrSlug: $idOrSlug) {
                    id
                    title
                    slug
                    inviteOnly
                    participants {
                        fullName
                    }
                    startDateTime
                    endDateTime
                    locationDetails {
                        completeAddress
                        city
                        state
                        country
                        geolocation {
                            latitude
                            longitude
                        }
                    }
                    description
                    permission
                    videoCallLink {
                        url
                        additionalInfo
                    }
                    creator {
                        fullName
                    }
                    isHybrid
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "idOrSlug": id_or_slug,
        },
    )


def delete_appointment(user, appointment_id):
    return async_to_sync(schema.execute)(
        """
        mutation test($appointmentId: UUID!){
            deleteAppointment(appointmentId: $appointmentId) {
                success
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"appointmentId": str(appointment_id)},
    )


def update_input_data(appointment_id, input_data):
    data = input_data.copy()
    data.pop("spaceId", None)
    data["appointmentId"] = appointment_id
    return data
