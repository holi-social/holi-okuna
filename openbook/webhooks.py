import json
import structlog

from django.http import JsonResponse
from django.views import View
from requests.exceptions import HTTPError
from rest_framework.authentication import TokenAuthentication
from django.core.exceptions import ValidationError

from openbook_auth.models import User
from openbook_notifications.payloads import NotificationType
from openbook_notifications.api import NotificationApi

logger = structlog.get_logger(__name__)


class NotificationWebhook(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            notification_type = data["payload"]["notificationType"]
            logger.info(f"Processing Notification Webhook for notification type: {notification_type}")

            if notification_type:
                handler = NotificationWebhookHandlerFactory.create_handler(notification_type)
                if handler:
                    return handler.handle(data)
                else:
                    return JsonResponse({"message": "Unknown notificationType"}, status=400)
            else:
                return JsonResponse({"message": "notificationType is missing"}, status=400)
        except KeyError:
            return JsonResponse({"message": "Invalid payload"}, status=400)


class NotificationWebhookHandlerFactory:
    @staticmethod
    def create_handler(notification_type):
        if notification_type == NotificationType.SPACE_MEMBERSHIP_REQUEST.value:
            return SpaceMembershipRequestNotificationHandler()
        else:
            return None


class SpaceMembershipRequestNotificationHandler:
    def handle(self, data):
        try:
            username = data["subscriber"]["subscriberId"]
            space_name = data["payload"]["data"]["space"]["name"]
            user = User.objects.get(username=username)
            user_is_admin = user.is_administrator_of_community_with_name(space_name)
            return JsonResponse({"valid": user_is_admin}, status=200)
        except User.DoesNotExist:
            return JsonResponse({"valid": False}, status=200)
        except KeyError:
            return JsonResponse({"valid": False}, status=200)


class OryWebhook(View):
    def post(self, request):
        # this will check, that the request has an Authentication header with a valid Token for an existing user in Django.
        # Ory Webhook requests needs to contain an auth token prefixed with "Token". Tokens can be seen via admin portal or in the DB.
        TokenAuthentication().authenticate(request)

        data = json.loads(request.body)
        logger.info(f"Processing Ory Webhook for user: {data['id']}")

        # Update user e-mail
        user = User.objects.get(username=data["id"])
        user.email = data["email"]
        try:
            user.save()
        except ValidationError as error:
            if "User with this Email address already exists." in error.message_dict["email"]:
                return JsonResponse(
                    {
                        "messages": [
                            {
                                "instance_ptr": "#/traits/email",  # Points to the field that failed validation.
                                "messages": [
                                    {
                                        "id": 8000001,  # Unique numeric ID of the error that helps the frontend to interpret this message.
                                        "text": "The email address is already taken",
                                        "type": "error",
                                    }
                                ],
                            }
                        ]
                    },
                    status=400,
                )
        try:
            subscriber = NotificationApi.find_subscriber(user_id=user.username)
            NotificationApi.update_subscriber(user=user, locale=subscriber.locale)
        except HTTPError as http_err:
            if http_err.response.status_code == 404:
                # We can not create the subscriber in novu, as we don't know the users locale
                logger.debug("Could not update e-mail in novu as the subscriber does not exist yet")
            else:
                raise http_err

        return JsonResponse({}, status=200)
