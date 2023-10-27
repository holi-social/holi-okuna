import json

from django.http import JsonResponse
from django.views import View

from openbook_notifications.payloads import NotificationType


class NotificationWebhook(View):
    def post(self, request):
        print(request)
        data = json.loads(request.body)
        notification_type = data["payload"]["notification_type"]

        if notification_type:
            handler = NotificationWebhookHandlerFactory.create_handler(notification_type)
            if handler:
                return handler.handle(data)
            else:
                return JsonResponse({"message": "Unknown notification_type"}, status=400)
        else:
            return JsonResponse({"message": "notification_type is missing"}, status=400)


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
