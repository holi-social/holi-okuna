import uuid
from copy import deepcopy

import requests
import strawberry
import structlog
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from graphql import GraphQLError
from rest_framework.exceptions import ValidationError

from openbook.helpers import (
    publish_space_deleted_event,
    publish_user_deleted_event,
    publish_user_name_updated_event,
)
from openbook.utils import invalidate_discover_spaces_query_cache
from openbook_auth.models import User as UserModel
from openbook_auth.schema.types import UpdateAuthenticatedUserInput, User, RegisterDeviceInput
from openbook_auth.serializers.authenticated_user_serializers import (
    UpdateAuthenticatedUserSerializer,
)
from openbook_auth.tasks import update_ory_user_identity, update_ory_user_names
from openbook_auth.utils import verify_authorized_user
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.helpers import is_parameter_null, to_input_dict
from openbook_common.schema.types import Result
from openbook_devices.enums import DeviceType
from openbook_notifications.api import NotificationApi
from openbook_notifications.enums import NotificationProvider
from openbook_devices.serializers import RegisterDeviceSerializer

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def update_authenticated_user(self, info, input: UpdateAuthenticatedUserInput) -> User:
        current_user = verify_authorized_user(info)

        input_dict = to_input_dict(input)
        if input.first_name:
            input_dict["name"] = input.first_name

        # TODO: Only for temporary backwards compatibility, remove in HOLI-4353
        if input.geolocation and "properties" not in input.geolocation:
            input_dict.pop("geolocation")

        serializer = UpdateAuthenticatedUserSerializer(data=input_dict)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        remove_avatar = is_parameter_null(data, "avatar")

        current_user.update(
            name=data.get("name"),
            last_name=data.get("last_name"),
            about_me=data.get("about_me"),
            pronouns=data.get("pronouns"),
            location=data.get("location"),
            geolocation=data.get("geolocation"),
            update_location=input.location is not strawberry.UNSET or input.geolocation is not strawberry.UNSET,
            engagement_level=data.get("engagement_level"),
            interests=data.get("interests"),
            sdgs=data.get("sdgs"),
            skills=data.get("skills"),
            avatar=data.get("avatar"),
            remove_avatar=remove_avatar,
            save=True,
        )

        if input.first_name or input.last_name:
            update_ory_user_names(current_user.id)
            publish_user_name_updated_event(user=current_user)

        # set identity when needed
        if not current_user.identity and input.first_name:
            current_user.identity = UserModel.sanitize_identity_input(input.first_name)

            if (
                UserModel.is_invalid_identity(current_user.identity)
                or UserModel.is_identity_taken(current_user.identity)
                or not update_ory_user_identity(current_user)
            ):
                identity_wish = UserModel.sanitize_identity_input(current_user.profile.full_name())
                # when the user has no last name, full_name is identical to first_name, so init the counter with 0
                # to already start adding a number on the call to next_unique_identity.
                # Otherwise init with None, to not add a number on the first call to next_unique_identity
                counter = None if identity_wish != current_user.identity else 0
                tries = 0
                taken_identities = UserModel.get_taken_identities(identity_wish)
                while True:
                    current_user.identity, counter = UserModel.next_unique_identity(
                        identity_wish, taken_identities, counter
                    )
                    if update_ory_user_identity(current_user):
                        break  # Ory update was successful, and there was no collision. We are done.
                    tries += 1
                    if tries > 10:
                        logger.error("Could not generate identity from user name after %s attempts.", tries)
                        raise ValidationError({"identity": _("Could not generate identity from user names.")})

            current_user.save()

        cache.set(f"{settings.USER_CACHE_PREFIX}{current_user.username}", current_user, timeout=300)

        return current_user

    @strawberry.mutation
    @sync_to_async
    def delete_authenticated_user(self, info) -> Result:
        current_user = verify_authorized_user(info)
        headers = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}
        logger.info(f"Deleting user {current_user.username}...")

        response = requests.delete(
            f"{settings.ORY_BASE_URL}/admin/identities/{current_user.username}",
            headers=headers,
        )
        # Ory returns 204 in case of success
        if not response.ok:
            error_message = response.error.error if response.error else "Unknown"
            raise Exception(f"Deleting user {current_user.username} in ory failed: {error_message}")

        # crude hack to prevent concurrent user references (e.g. mentions in comments) to let the user deletion fail
        # we just retry a couple of times
        for count in range(3, -1, -1):
            try:
                exclusive_administrated_communities = list(current_user.get_exclusive_administrated_communities())

                current_user.delete()
                publish_user_deleted_event(user=current_user)
                logger.info(f"Successfully deleted user {current_user.username}")

                logger.warning(f"All spaces exclusively administered by {current_user.username} will be deleted")

                if exclusive_administrated_communities:
                    for space in exclusive_administrated_communities:
                        # Make a copy of the space before deleting it to pass it as a SpaceDeleted event payload
                        space_to_delete = deepcopy(space)
                        space.delete()
                        publish_space_deleted_event(space_to_delete)

                    invalidate_discover_spaces_query_cache()

                return Result(success=True)
            except (Exception,):
                logger.warning(
                    f"Could not delete user with id {current_user.username}, retrying #{count} more times",
                    exc_info=True,
                )
                if count == 0:
                    logger.exception(
                        f"Could not delete user with id {current_user.username}, no more retries, failing"
                    )
                    raise GraphQLError(
                        "Unable to delete user in okuna",
                        extensions={"code": GraphQLErrorCodes.INTERNAL_SERVER_ERROR},
                    )

    @strawberry.mutation
    @sync_to_async
    def block_user(self, info, user_id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)
        username_of_user_to_block = str(user_id)

        current_user.block_user_with_username(username_of_user_to_block)

        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def register_device(self, info, input: RegisterDeviceInput) -> Result:
        current_user = verify_authorized_user(info)

        input_dict = to_input_dict(input)
        serializer = RegisterDeviceSerializer(data=input_dict)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        token = data.get("token")
        device_type = data.get("device_type")
        user_id = str(current_user.username)

        if not current_user.has_device_with_token_and_type(token=token, device_type=device_type):
            current_user.create_device(token=token, device_type=device_type)
            provider_id = (
                NotificationProvider.APNS.value
                if device_type == DeviceType.IOS.value
                else NotificationProvider.FCM.value
            )
            # Register device token
            NotificationApi.set_subscriber_credentials(user_id=user_id, provider_id=provider_id, device_tokens=[token])

        return Result(success=True)
