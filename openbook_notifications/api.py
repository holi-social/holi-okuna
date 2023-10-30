from typing import List, Optional
from requests.exceptions import HTTPError
import structlog

from novu.api.subscriber import SubscriberApi
from novu.dto.subscriber import SubscriberDto

from openbook_auth.models import User
from openbook_notifications.toggles import notifications_toggle
from openbook_notifications.enums import NotificationProvider

logger = structlog.get_logger(__name__)


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
    def set_subscriber_credentials(
        subscriber_id: str,
        provider_id: NotificationProvider,
        webhook_url: str | None = None,
        device_tokens: List[str] | None = None,
    ):
        # need to delete old credentials first. otherwise, an old push token might stick around on novu and novu will
        # try to use the old push token to deliver a message and as a result, fail to do so
        log_info = {"subscriber_id": subscriber_id, "provider_id": provider_id}
        logger.debug("Deleting old subscriber credentials for %s", log_info)
        SubscriberApi().delete_credentials(subscriber_id, provider_id.value)
        logger.debug("Setting new subscriber credentials for %s", log_info)
        return SubscriberApi().credentials(subscriber_id, provider_id.value.value, webhook_url, device_tokens)

    @staticmethod
    @notifications_toggle
    def delete_subscriber(user_id: str):
        return SubscriberApi().delete(subscriber_id=str(user_id))
