from django.db import Error
from graphql import GraphQLError
from strawberry_django_plus import gql

from openbook_auth import helpers as auth_helpers
from openbook_auth import models as auth_models
from openbook_auth import tasks as auth_tasks
from openbook_auth.images import delete_avatar
from openbook_auth.schema import inputs as auth_inputs
from openbook_auth.schema import types as auth_types
from openbook_auth.schema.types import UpdateConnectionAction
from openbook_auth.views.authenticated_user import serializers as auth_serializers
from openbook_common.utils import helpers


@gql.type
class Mutation:
    @gql.mutation
    def update_authenticated_user(self, info, input: auth_inputs.UpdateAuthenticatedUserInput) -> auth_types.User:
        current_user = auth_helpers.verify_authorized_user(info)
        update_avatar = False

        if input.avatar:
            if input.avatar in ("", {}):
                raise GraphQLError(
                    f"Attribute 'avatar' should be missing or contain a file, but was: '{input.avatar}'"
                )
            else:
                update_avatar = True

        input_dict = helpers.to_input_dict(input)
        if input.first_name:
            input_dict["name"] = input.first_name

        serializer = auth_serializers.UpdateAuthenticatedUserSerializer(data=input_dict)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            current_user.update(
                name=data.get("name"),
                last_name=data.get("last_name"),
                about_me=data.get("about_me"),
                pronouns=data.get("pronouns"),
                location=data.get("location"),
                geolocation=(auth_inputs.GeolocationInput.to_point(data.get("geolocation"))),
                engagement_level=data.get("engagement_level"),
                interests=data.get("interests"),
                sdgs=data.get("sdgs"),
                skills=data.get("skills"),
                avatar=data.get("avatar"),
                update_avatar=update_avatar,
                save=True,
            )
        except Error:
            if update_avatar:
                delete_avatar(data["avatar"])
            raise

        if input.first_name or input.last_name:
            auth_tasks.update_ory_user.delay(current_user.id)

        return current_user

    @gql.mutation
    def update_connection_with_user(self, info, input: auth_inputs.UpdateConnectionWithUserInput) -> auth_types.User:
        current_user = auth_helpers.verify_authorized_user(info)

        serializer = auth_serializers.UpdateConnectionWithUserSerializer(data=helpers.to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_to_connect_to = current_user.get_user_with_username(username=data.get("user_id"))

        current_connection_status = current_user.get_connection_status_with_user_id(user_id=user_to_connect_to.id)

        # Connect action
        if input.action == UpdateConnectionAction.CONNECT:
            # if current user needs to confirm connection, run confirm_connection_with_user_with_id
            if current_connection_status == auth_models.UserConnectionStatus.PENDING_CONFIRMATION:
                current_user.confirm_connection_with_user_with_id(user_id=user_to_connect_to.id)

            # if there is no connection yet (no requests or pending confirmation), run connect_with_user_with_id
            if current_connection_status == auth_models.UserConnectionStatus.NOT_CONNECTED:
                current_user.connect_with_user_with_id(user_id=user_to_connect_to.id)

        # Disconnect action (only run if current connection status is different than NOT_CONNECTED)
        elif (
            input.action == UpdateConnectionAction.DISCONNECT
            and current_connection_status != auth_models.UserConnectionStatus.NOT_CONNECTED
        ):
            current_user.disconnect_from_user_with_id(user_id=user_to_connect_to.id)

        return user_to_connect_to
