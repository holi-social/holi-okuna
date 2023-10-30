import json
import structlog

from django.http import JsonResponse
from django.views import View

from openbook_notifications.payloads import NotificationType

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
        data = json.loads(request.body)
        logger.info(f"Ory Webhook: {data}")
        return JsonResponse({}, status=200)
