import json
import structlog

from django.http import JsonResponse
from django.views import View
from rest_framework import exceptions
from requests.exceptions import HTTPError
from rest_framework.authtoken.models import Token
from openbook_auth.models import User
from openbook_notifications.payloads import NotificationType
from openbook_notifications.api import NotificationApi
from django.utils.translation import gettext_lazy as _

logger = structlog.get_logger(__name__)


class NotificationWebhook(View):
    def post(self, request):
        print(request)
        data = json.loads(request.body)
        notification_type = data["payload"]["notificationType"]

        if notification_type:
            handler = NotificationWebhookHandlerFactory.create_handler(notification_type)
            if handler:
                return handler.handle(data)
            else:
                return JsonResponse({"message": "Unknown notificationType"}, status=400)
        else:
            return JsonResponse({"message": "notificationType is missing"}, status=400)


class NotificationWebhookHandlerFactory:
    @staticmethod
    def create_handler(notification_type):
        if notification_type == NotificationType.SPACE_MEMBERSHIP_REQUEST.value:
            return SpaceMembershipRequestNotificationHandler()
        else:
            return None


class SpaceMembershipRequestNotificationHandler:
    def handle(self, data):
        pass


class OryWebhook(View):
    def post(self, request):
        self.check_bearer_token(request)

        data = json.loads(request.body)
        logger.info(f"Processing Ory Webhook for user: {data['id']}")

        # Update user e-mail
        user = User.objects.get(username=data["id"])
        user.email = data["email"]
        user.save()

        try:
            subscriber = NotificationApi.find_subscriber(user_id=user.username)
            NotificationApi.update_subscriber(user=user, locale=subscriber.locale)
        except HTTPError as http_err:
            if http_err.response.status_code == 404:
                # We can not create the subscriber in novu, as we don't know the users locale
                logger.debug(f"Could not update e-mail in novu as the subscriber does not exist yet")
            else:
                raise http_err

        return JsonResponse({}, status=200)

    def check_bearer_token(self, request):
        auth_header = request.META.get("HTTP_AUTHENTICATION")
        if not auth_header:
            raise exceptions.AuthenticationFailed(_("No Authentication header."))
        auth = request.META.get("HTTP_AUTHENTICATION").split()
        if len(auth) != 2 or auth[0].lower() != "bearer":
            raise exceptions.AuthenticationFailed(_("Wrong Authentication header."))
        try:
            token = Token.objects.select_related("user").get(key=auth[1])
            if not token.user.is_active:
                raise exceptions.AuthenticationFailed(_("User inactive or deleted."))
        except Token.DoesNotExist:
            raise exceptions.AuthenticationFailed(_("Invalid token."))
