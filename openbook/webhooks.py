import base64
import json

import structlog

from django.http import JsonResponse, HttpRequest
from django.views import View
from google.oauth2 import id_token
from google.auth.transport import requests
from requests.exceptions import HTTPError
from rest_framework.authentication import TokenAuthentication
from django.core.exceptions import ValidationError

from favorites.events import ExternalDataEventHandler
from openbook.settings import environment_checker
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


class PubSubPushEndpoint(View):
    @property
    def running_in_local_setup(self):
        return environment_checker.is_development()

    def post(self, request: HttpRequest, topic_name: str = None):
        if self.is_authorized(request):
            try:
                envelope = json.loads(request.body)
                pubsub_message = envelope.get("message", {})
                message_data = pubsub_message.get("data")
                if message_data:
                    decoded_data = json.loads(base64.b64decode(message_data).decode("utf-8"))

                    logger.info(f"Received PubSub message for topic {topic_name}: {decoded_data}")

                    if "external-data" in topic_name:
                        # external-data-local
                        # external-data-staging
                        # external-data-production
                        if not ExternalDataEventHandler.handle_event(decoded_data):
                            logger.warning(f"Event for topic {topic_name} was not handled successfully")
                            return JsonResponse({"message": "Event not handled"}, status=500)
                    else:
                        logger.warning(f"Unhandled topic: {topic_name}")
                        return JsonResponse({"message": f"Unhandled topic: {topic_name}"}, status=400)

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                return JsonResponse({"message": "Error processing message"}, status=500)

            logger.info(f"Successfully processed message for topic {topic_name}")
            return JsonResponse({"status": "OK"}, status=200)
        else:
            return JsonResponse({"message": "Authentication failed"}, status=401)

    def is_authorized(self, request: HttpRequest) -> bool:
        if self.running_in_local_setup:
            logger.info("granting auth, running locally")
            return True

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.error("Missing Authorization header")
            return False

        try:
            _, token = auth_header.split()
            token = id_token.verify_oauth2_token(
                token,
                requests.Request(),
            )

            # todo gregor: for debugging, remove later
            logger.info(f"Token: {token}")

            return True

        except Exception as e:
            logger.error(f"Invalid token: {str(e)}")
            return False
