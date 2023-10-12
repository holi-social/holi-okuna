from typing import List, Optional
from requests.exceptions import HTTPError

from novu.api.subscriber import SubscriberApi
from novu.dto.subscriber import SubscriberDto

from openbook_auth.models import User
from openbook_notifications.toggles import notifications_toggle


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

        return SubscriberApi().put(subscriber)

    @staticmethod
    @notifications_toggle
    def set_subscriber_credentials(
        user_id: str, provider_id: str, webhook_url: str | None = None, device_tokens: List[str] | None = None
    ):
        return SubscriberApi().credentials(user_id, provider_id, webhook_url, device_tokens)

    @staticmethod
    @notifications_toggle
    def delete_subscriber(user_id: str):
        return SubscriberApi().delete(subscriber_id=str(user_id))
