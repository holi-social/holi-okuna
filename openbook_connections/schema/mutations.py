import strawberry
from asgiref.sync import sync_to_async

from openbook_auth.models import UserConnectionStatus
from openbook_auth.schema.types import UpdateConnectionWithUserInput, User
from openbook_auth.utils import verify_authorized_user
from openbook_common.helpers import to_input_dict
from openbook_communities.enums import UpdateConnectionAction
from openbook_connections.serializers import UpdateConnectionWithUserSerializer


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def update_connection_with_user(self, info, input: UpdateConnectionWithUserInput) -> User:
        current_user = verify_authorized_user(info)

        serializer = UpdateConnectionWithUserSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_to_connect_to = current_user.get_user_with_username(username=data.get("user_id"))

        current_connection_status = current_user.get_connection_status_with_user_id(user_id=user_to_connect_to.id)

        # Connect action
        if input.action == UpdateConnectionAction.CONNECT:
            # if current user needs to confirm connection, run confirm_connection_with_user_with_id
            if current_connection_status == UserConnectionStatus.PENDING_CONFIRMATION:
                current_user.confirm_connection_with_user_with_id(user_id=user_to_connect_to.id)

            # if there is no connection yet (no requests or pending confirmation), run connect_with_user_with_id
            if current_connection_status == UserConnectionStatus.NOT_CONNECTED:
                current_user.connect_with_user_with_id(user_id=user_to_connect_to.id)

        # Disconnect action (only run if current connection status is different than NOT_CONNECTED)
        elif (
            input.action == UpdateConnectionAction.DISCONNECT
            and current_connection_status != UserConnectionStatus.NOT_CONNECTED
        ):
            current_user.disconnect_from_user_with_id(user_id=user_to_connect_to.id)

        return user_to_connect_to
