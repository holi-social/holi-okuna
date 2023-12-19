from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from requests.exceptions import HTTPError
import structlog

from novu.api.message import MessageApi
from novu.api.event import EventApi
from novu.api.subscriber import SubscriberApi
from novu.dto.subscriber import SubscriberDto

from openbook_notifications.toggles import notifications_toggle
from openbook_notifications.enums import NotificationProvider, NotificationChannel

logger = structlog.get_logger(__name__)


if TYPE_CHECKING:
    from openbook_auth.models import User


class NotificationApi:
    @staticmethod
    @notifications_toggle
    def create_subscriber(user: User, locale: Optional[str]):
        subscriber = SubscriberDto(
            first_name=user.profile.name,
            last_name=user.profile.last_name,
            avatar=user.profile.avatar.url if user.profile.avatar else None,
            email=user.email,
            subscriber_id=str(user.username),
            locale=locale,
        )

        return SubscriberApi().create(subscriber)

    @staticmethod
    @notifications_toggle
    def find_subscriber(user_id: str):
        return SubscriberApi().get(subscriber_id=str(user_id))

    @staticmethod
    @notifications_toggle
    def find_or_create_subscriber(user: User, locale: Optional[str]):
        try:
            subscriber = NotificationApi.find_subscriber(user_id=user.username)
        except HTTPError as http_err:
            if http_err.response.status_code == 404:
                subscriber = NotificationApi.create_subscriber(user, locale)
            else:
                raise

        return subscriber

    @staticmethod
    @notifications_toggle
    def update_subscriber(user: User, locale: Optional[str]):
        subscriber = SubscriberDto(
            subscriber_id=str(user.username),
            first_name=user.profile.name,
            last_name=user.profile.last_name,
            avatar=user.profile.avatar.url if user.profile.avatar else None,
            email=user.email,
            locale=locale,
        )

        logger.debug("Updating subscriber info for %s", user.username)
        return SubscriberApi().put(subscriber)

    @staticmethod
    @notifications_toggle
    def create_or_update_subscriber(user: User, locale: Optional[str]):
        try:
            subscriber = NotificationApi.update_subscriber(user, locale)
        except HTTPError as http_err:
            status_code = http_err.response.status_code
            # Novu treats missing subscribers during update as "BAD REQUEST"
            if status_code == 404 or status_code == 400:
                subscriber = NotificationApi.create_subscriber(user, locale)
            else:
                raise

        return subscriber

    @staticmethod
    @notifications_toggle
    def set_subscriber_credentials(
        subscriber_id: str,
        provider_id: NotificationProvider,
        webhook_url: str | None = None,
        device_tokens: List[str] | None = None,
    ):
        logger.debug(
            "Setting new subscriber credentials for %s", {"subscriber_id": subscriber_id, "provider_id": provider_id}
        )
        return SubscriberApi().credentials(subscriber_id, provider_id.value.value, webhook_url, device_tokens)

    @staticmethod
    @notifications_toggle
    def delete_subscriber(user_id: str):
        try:
            return SubscriberApi().delete(subscriber_id=str(user_id))
        except HTTPError as http_err:
            if http_err.response.status_code == 404:
                # User was already deleted
                pass
            else:
                raise

    @staticmethod
    @notifications_toggle
    def cancel_workflow(transaction_id: str):
        EventApi().delete(transaction_id=transaction_id)

    @staticmethod
    @notifications_toggle
    def delete_in_app_messages(transaction_id: str, subscriber_id: str | None = None):
        messages = MessageApi().list(
            transaction_id=transaction_id,
            channel=NotificationChannel.IN_APP.value,
            subscriber_id=subscriber_id,
        )
        for message in messages.data:
            try:
                MessageApi().delete(message_id=message._id)
            except HTTPError as http_err:
                if http_err.response.status_code == 404:
                    # Message was already deleted
                    pass
                else:
                    raise

        # If there are more messages than fetched, perform deletion again
        # As we just deleted messages, we can start with page 0 again
        if messages.total_count > messages.page_size:
            NotificationApi.delete_in_app_messages(transaction_id=transaction_id, subscriber_id=subscriber_id)
