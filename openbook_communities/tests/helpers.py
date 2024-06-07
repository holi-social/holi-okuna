from typing import Optional
from uuid import UUID

from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema
from openbook_auth.models import User
from openbook_communities.enums import UpdateConnectionAction
from openbook_communities.models import Community, SpaceUserConnectionType
from openbook_posts.enums import VisibilityFilter


def mutate_invite_user_by_email(
    auth_user: User,
    space_id: UUID,
    email: str,
):
    return async_to_sync(schema.execute)(
        """
        mutation InviteToSpaceByEmail($email: String!, $spaceId: UUID!) {
            inviteToSpaceByEmail(email: $email, spaceId: $spaceId) {
                success
            }
        }
        """,
        context_value=benedict({"request": {"user": auth_user, "META": {"HTTP_ACCEPT_LANGUAGE": "de"}}}),
        variable_values=benedict(
            {
                "email": email,
                "spaceId": str(space_id),
            }
        ),
    )


def mutate_update_space_user_connection_raw(
    auth_user: User,
    space_id: UUID,
    connection_type: SpaceUserConnectionType,
    connect_action: UpdateConnectionAction,
    user_id: Optional[UUID] = None,
    message: Optional[str] = None,
):
    return async_to_sync(schema.execute)(
        """
        mutation ($spaceId: UUID!, $userId: UUID, $type: SpaceUserConnectionType!, $action: UpdateConnectionAction!, $message: String){
            updateSpaceUserConnection(spaceId: $spaceId,
                                        userId: $userId,
                                        connectionType: $type,
                                        connectAction: $action,
                                        message: $message) {
                id
                name
                members {
                    totalResults
                    data {
                        user {
                            id
                        }
                        isAdministrator
                    }
                }
                connectionStatusToMyself
            }
        }
        """,
        context_value=benedict({"request": {"user": auth_user}}),
        variable_values=benedict(
            {
                "spaceId": str(space_id),
                "userId": str(user_id) if user_id else None,
                "type": connection_type.value,
                "action": connect_action.value,
                "message": message,
            }
        ),
    )


def mutate_update_space_user_connection_data(
    auth_user: User,
    space_id: UUID,
    connection_type: SpaceUserConnectionType,
    connect_action: UpdateConnectionAction,
    user_id: Optional[UUID] = None,
    message: Optional[str] = None,
):
    response = mutate_update_space_user_connection_raw(
        auth_user, space_id, connection_type, connect_action, user_id, message
    )
    assert response.errors is None
    return response.data["updateSpaceUserConnection"]


def get_space_for_user(user: User, space: Community):
    response = async_to_sync(schema.execute)(
        """
        query($id:String!) {
            spaceById(idOrName:$id) {
                id
                name
                members {
                    totalResults
                    data {
                        user {
                            id
                        }
                        isAdministrator
                    }
                }
                connectionStatusToMyself
            }
        }
        """,
        variable_values={"id": str(space.id)},
        context_value=benedict({"request": {"user": user}}),
    )

    assert response.errors is None
    return response.data["spaceById"]


def get_space_by_id_with_posts(user: User, id: UUID, visibility: VisibilityFilter = VisibilityFilter.ALL):
    response = async_to_sync(schema.execute)(
        """
        query($id:String!, $visibility:VisibilityFilter!) {
            spaceById(idOrName:$id) {
                id
                name
                hasPublicPosts
                hasPrivatePosts
                posts(visibility:$visibility) {
                    totalResults
                    data {
                        id
                        title
                        isPublic
                        created
                    }
                }
            }
        }
        """,
        variable_values={"id": str(id), "visibility": visibility.value},
        context_value=benedict({"request": {"user": user}}),
    )

    assert response.errors is None
    return response.data["spaceById"]


def update_and_assert_onboarding_steps(user, community_id, onboarding_steps):
    update_space_mutation = """
        mutation test($input: UpdateSpaceInput!) {
            updateSpace(input: $input) {
                onboarding { steps { text } }
            }
        }
        """

    response = async_to_sync(schema.execute)(
        update_space_mutation,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "input": {
                "id": str(community_id),
                "onboardingSteps": onboarding_steps,
            }
        },
    )

    assert response.errors is None
    updated_space = response.data["updateSpace"]

    assert "onboarding" in updated_space
    assert "steps" in updated_space["onboarding"]
    new_onboarding_steps = updated_space["onboarding"]["steps"]
    assert updated_space["onboarding"]["steps"] == onboarding_steps


def assert_onboarding(community_id, user, expected):
    response = async_to_sync(schema.execute)(
        """
        query($id:String!) {
            spaceById(idOrName:$id) {
                onboarding { steps { text } }
            }
        }
        """,
        variable_values={"id": str(community_id)},
        context_value=benedict({"request": {"user": user}}),
    )

    assert response.data["spaceById"]["onboarding"] == expected


def assert_collaboration_tools(community_id, user, expected):
    response = async_to_sync(schema.execute)(
        """
        query($id:String!) {
            spaceById(idOrName:$id) {
                collaborationTools { id }
            }
        }
        """,
        variable_values={"id": str(community_id)},
        context_value=benedict({"request": {"user": user}}),
    )

    assert response.data["spaceById"]["collaborationTools"] == expected


def get_space_by_id_with_appointments_raw(space_id, user):
    return async_to_sync(schema.execute)(
        """
        query($id:String!) {
            spaceById(idOrName:$id) {
                id
                name
                appointments {
                    totalResults
                    data {
                        id
                        inviteOnly
                        title
                        description
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
                        videoCallLink {
                            url
                            additionalInfo
                        }
                        isHybrid
                        hasVideoCallLink
                    }
                }
            }
        }
        """,
        variable_values={"id": str(space_id)},
        context_value=benedict({"request": {"user": user}}),
    )


def get_space_by_id_with_appointments(space_id, user):
    response = get_space_by_id_with_appointments_raw(space_id, user)
    assert response.errors is None
    return response.data["spaceById"]
