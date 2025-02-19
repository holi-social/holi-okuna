# ruff: noqa
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Dict, List

import requests
import strawberry
import structlog
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db.models import When, Value, Count, Case, IntegerField
from django.utils.translation import get_language_from_request
from graphql import GraphQLError
from rest_framework.exceptions import ValidationError

from openbook_common.tracking import track, TrackingEvent
from openbook_communities.events import publish_space_deleted_event
from openbook_auth.events import (
    publish_user_deleted_event,
    publish_user_name_updated_event,
    publish_user_updated_event,
)
from openbook.utils import invalidate_discover_spaces_query_cache
from openbook_auth.models import User as UserModel
from favorites.models import UserFavorite
from openbook_auth.schema.types import UpdateAuthenticatedUserInput, User, AuthenticatedUser, RegisterDeviceInput
from openbook_auth.serializers.authenticated_user_serializers import (
    UpdateAuthenticatedUserSerializer,
)
from openbook_auth.tasks import update_ory_user_names, generate_identity_when_needed
from openbook_auth.utils import verify_authorized_user
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.helpers import is_parameter_null, to_input_dict
from openbook_common.schema.types import Result
from openbook_common.utils.model_loaders import get_insight_model, get_community_model, get_topic_model
from openbook_communities.schema.helpers import create_filtered_spaces_query
from openbook_notifications.api import NotificationApi
from openbook_notifications.enums import NotificationProvider
from openbook_devices.serializers import RegisterDeviceSerializer
from openbook_notifications.services import NotificationsService

logger = structlog.get_logger(__name__)


def _capture_user_fields(user: UserModel) -> Dict[str, str]:
    # for many-to-many relations (interests, sdgs, skills), only capture ids to avoid db round-trips
    return {
        "email": user.email,
        "firstName": user.profile.name,
        "lastName": user.profile.last_name,
        "location": user.profile.location,
        "geolocation": user.profile.geolocation,
        "aboutMe": user.profile.about_me,
        "pronouns": user.profile.pronouns,
        "engagementLevel": user.profile.engagement_level,
        "interests": set(user.profile.interests.values_list("id", flat=True)),
        "sdgs": set(user.profile.sdgs.values_list("id", flat=True)),
        "skills": set(user.profile.skills.values_list("id", flat=True)),
        "avatar": user.profile.avatar.url if user.profile.avatar else None,
    }


def _get_updated_fields(o1: Dict[str, any], o2: Dict[str, any]) -> List[str]:
    return [key for key in set(o1.keys()).union(o2.keys()) if o1.get(key) != o2.get(key)]


@strawberry.type
class Mutation:
    # TODO HOLI-8088 remove once not used by the frontend anymore
    @strawberry.mutation(deprecation_reason="Deprecated in favor of 'updateAuthenticatedUserV2'.")
    def update_authenticated_user(self, info, input: UpdateAuthenticatedUserInput) -> User:
        return Mutation().update_authenticated_user_v2(info, input)

    @strawberry.mutation
    @sync_to_async
    def update_authenticated_user_v2(self, info, input: UpdateAuthenticatedUserInput) -> AuthenticatedUser:
        current_user = verify_authorized_user(info)

        user_entity = UserModel.objects.get(username=current_user.username)
        user_current_name = user_entity.profile.name

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
        current_user_fields_before = _capture_user_fields(current_user)

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
            tracking_consent_analytics=data.get("tracking_consent_analytics"),
            tracking_consent_personalization=data.get("tracking_consent_personalization"),
            save=True,
        )
        current_user_fields_after = _capture_user_fields(current_user)

        generate_identity_when_needed(current_user)

        if input.first_name or input.last_name or input.avatar or remove_avatar:
            update_ory_user_names(current_user.id)
            publish_user_name_updated_event(user=current_user)

        publish_user_updated_event(user=current_user)

        locale = get_language_from_request(info.context.request)
        NotificationApi.create_or_update_subscriber(user=current_user, locale=locale)

        user_updated_name = current_user.profile.name

        # send welcome email only for newly created users
        # include recommended spaces and latest insights in the welcome email
        if user_current_name is None and user_updated_name is not None:
            community_model = get_community_model()
            insight_model = get_insight_model()
            topic_model = get_topic_model()

            whens = []
            topic_ids = list(current_user.profile.interests.values_list("id", flat=True).all())
            geolocation = current_user.geolocation

            if topic_ids:
                whens.append(
                    When(create_filtered_spaces_query(topic_ids=topic_ids, geolocation=geolocation), then=Value(10))
                )

            if geolocation:
                whens.append(When(create_filtered_spaces_query(geolocation=geolocation), then=Value(20)))

            default_topics = list(
                topic_model.objects.filter(is_discover_spaces_default=True).values_list("id", flat=True)
            )
            if default_topics:
                whens.append(When(create_filtered_spaces_query(topic_ids=default_topics), then=Value(30)))

            spaces = (
                community_model.objects.prefetch_related("links", "memberships__user__profile")
                .annotate(member_count=Count("memberships"))
                .annotate(
                    custom_order=Case(
                        *whens,
                        output_field=IntegerField(),
                    )
                )
                .filter(custom_order__isnull=False, is_deleted=False)
                .distinct()
                .order_by("custom_order", "-created")[:4]
            )

            insights = insight_model.objects.order_by("-date_published")[:3]

            subscription_token = str(uuid.uuid4())

            NotificationsService.send_welcome_email_series_notification(
                user=current_user, spaces=spaces, insights=insights, token=subscription_token
            )

        updated_fields = _get_updated_fields(current_user_fields_before, current_user_fields_after)
        if updated_fields:
            track(current_user, TrackingEvent("userUpdated", {"updatedFields": updated_fields}))

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

        track(current_user, TrackingEvent("userDeleted"))

        # crude hack to prevent concurrent user references (e.g. mentions in comments) to let the user deletion fail
        # we just retry a couple of times
        for count in range(3, -1, -1):
            try:
                exclusive_administrated_communities = list(current_user.get_exclusive_administrated_communities())

                current_user.delete_pending_notifications()
                NotificationApi.delete_subscriber(user_id=current_user.username)
                current_user.delete()
                publish_user_deleted_event(user=current_user)
                logger.info(f"Successfully deleted user {current_user.username}")

                logger.warning(f"All spaces exclusively administered by {current_user.username} will be deleted")

                if exclusive_administrated_communities:
                    for space in exclusive_administrated_communities:
                        # Make a copy of the space before deleting it to pass it as a SpaceDeleted event payload
                        space_to_delete = deepcopy(space)
                        space.delete_pending_notifications()
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
        subscriber_id = str(current_user.username)

        logger.debug(
            "register_device %s %s",
            input,
            current_user.has_device_with_token_and_type(token=token, device_type=device_type),
        )

        # a device token can only be in Okuna if it has previously succeeded setting in Novu, so:
        # if a device token is in not in Okuna, it is also (most likely) not in Novu, and we have to update it in both
        if not current_user.has_device_with_token_and_type(token=token, device_type=device_type):
            provider_id = NotificationProvider.get_by_device_type(device_type)
            # Create subscriber if it doesn't exist already
            locale = get_language_from_request(info.context.request)
            NotificationApi.find_or_create_subscriber(user=current_user, locale=locale)
            NotificationApi.set_subscriber_credentials(
                subscriber_id=subscriber_id, provider_id=provider_id, device_tokens=[token]
            )
            current_user.create_device(token=token, device_type=device_type)

        return Result(success=True)

    @strawberry.mutation(deprecation_reason="Use 'favorite' mutation instead. Keep for version <=1.14.5")
    @sync_to_async
    def bookmark_insight(self, info, insight_id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)
        current_user.bookmark_insight(insight_id)  # To maintain compatibility with older versions
        UserFavorite.favorite(user=current_user, favoritable_id=insight_id, favoritable_type="insight")
        return Result(success=True)

    @strawberry.mutation(deprecation_reason="Use 'unfavorite' mutation instead. Keep for version <=1.14.5")
    @sync_to_async
    def remove_insight_bookmark(self, info, insight_id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)
        current_user.remove_insight_bookmark(insight_id)  # To maintain compatibility with older versions
        UserFavorite.unfavorite(user=current_user, favoritable_id=insight_id, favoritable_type="insight")
        return Result(success=True)

    @strawberry.mutation()
    @sync_to_async
    def unsubscribe_from_newsletter(self, info, token: str) -> Result:
        NotificationApi.cancel_workflow(transaction_id=token)
        return Result(success=True)
