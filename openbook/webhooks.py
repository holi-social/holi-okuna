import base64
import json

import structlog
import requests
from typing import Dict, Optional, List
from django.conf import settings

from django.http import JsonResponse, HttpRequest
from django.views import View
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from requests.exceptions import HTTPError
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import ValidationError

from openbook_common.pubsub.incoming_event import IncomingEvent
from openbook_common.pubsub.handler import ExternalDataEventHandler
from openbook.settings import environment_checker
from openbook_auth.models import User
from openbook_notifications.payloads import NotificationType
from openbook_notifications.api import NotificationApi
from openbook_common.tracking import posthog

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
        except Exception as e:
            logger.error(f"Error processing notification webhook: {str(e)}")
            return JsonResponse({"message": "Internal server error"}, status=500)


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


class AppcuesWebhook(View):
    def post(self, request):
        try:
            data = json.loads(request.body)

            event_name = data.get("name")
            user_id = data.get("user_id")
            timestamp = data.get("timestamp")

            if not event_name:
                return JsonResponse({"message": "Event name is missing"}, status=400)

            if not user_id:
                return JsonResponse({"message": "User ID is missing"}, status=400)

            return self._handle_appcues_event(user_id, event_name, timestamp)

        except json.JSONDecodeError:
            logger.error("Invalid JSON payload in Appcues webhook")
            return JsonResponse({"message": "Invalid JSON payload"}, status=400)
        except Exception as e:
            logger.error(f"Error processing Appcues webhook: {str(e)}")
            return JsonResponse({"message": "Internal server error"}, status=500)

    def _handle_appcues_event(self, appcues_user_id: str, event_name: str, timestamp: int):
        try:
            if appcues_user_id.startswith("anon:"):
                return JsonResponse({"message": "Skipped anonymous user"}, status=200)

            user_segments = self._fetch_user_segments(appcues_user_id)
            if user_segments is None:
                logger.warning(f"Could not fetch segments for Appcues user {appcues_user_id}")
                return JsonResponse({"message": "Could not fetch user segments"}, status=500)

            segments_mapping = self._fetch_segments_mapping()
            if segments_mapping is None:
                logger.warning("Could not fetch segments mapping from Appcues")
                return JsonResponse({"message": "Could not fetch segments mapping"}, status=500)

            self._update_posthog_with_segments(appcues_user_id, user_segments, segments_mapping, event_name, timestamp)

            logger.info(f"Successfully synced segments for user {appcues_user_id} from Appcues event {event_name}")
            return JsonResponse({"message": "User segments synced successfully"}, status=200)

        except Exception as e:
            logger.error(f"Error handling Appcues event: {str(e)}")
            return JsonResponse({"message": "Error processing Appcues event"}, status=500)

    def _fetch_user_segments(self, user_id: str) -> Optional[Dict]:
        if not settings.APPCUES_API_KEY or not settings.APPCUES_API_SECRET or not settings.APPCUES_ACCOUNT_ID:
            logger.warning("Appcues API credentials not configured")
            return None

        try:
            url = f"{settings.APPCUES_BASE_URL}/v2/accounts/{settings.APPCUES_ACCOUNT_ID}/users/{user_id}/profile"
            auth = (settings.APPCUES_API_KEY, settings.APPCUES_API_SECRET)
            headers = {"Content-Type": "application/json"}

            response = requests.get(url, auth=auth, headers=headers, timeout=10)
            response.raise_for_status()

            user_profile = response.json()

            segments = {}
            for key, value in user_profile.items():
                if key.startswith("_segment_"):
                    segment_id = key.replace("_segment_", "")
                    segments[segment_id] = value

            return segments

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching user segments from Appcues API: {str(e)}")
            return None

    def _fetch_segments_mapping(self) -> Optional[Dict[str, str]]:
        if not settings.APPCUES_API_KEY or not settings.APPCUES_API_SECRET or not settings.APPCUES_ACCOUNT_ID:
            logger.warning("Appcues API credentials not configured")
            return None

        try:
            url = f"{settings.APPCUES_BASE_URL}/v2/accounts/{settings.APPCUES_ACCOUNT_ID}/segments"
            auth = (settings.APPCUES_API_KEY, settings.APPCUES_API_SECRET)
            headers = {"Content-Type": "application/json"}

            response = requests.get(url, auth=auth, headers=headers, timeout=10)
            response.raise_for_status()

            segments = response.json()

            mapping = {}
            for segment in segments:
                mapping[segment["id"]] = segment["name"]

            return mapping

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching segments mapping from Appcues API: {str(e)}")
            return None

    def _update_posthog_with_segments(
        self, distinct_id: str, user_segments: Dict, segments_mapping: Dict[str, str], event_name: str, timestamp: int
    ):
        try:
            if not posthog:
                logger.warning("PostHog client not initialized, skipping property update")
                return

            active_segment_names = []

            for segment_id, segment_timestamp in user_segments.items():
                segment_name = segments_mapping.get(segment_id, segment_id)

                if segment_timestamp is not None:
                    active_segment_names.append(segment_name)

            user_properties = {"appcues_segments": active_segment_names}

            posthog.capture(
                distinct_id=distinct_id,
                event="Appcues",
                properties={
                    "$set": user_properties,
                    "event_name": event_name,
                    "user_id": distinct_id,
                    "active_segments": active_segment_names,
                    "timestamp": timestamp,
                },
            )

            logger.info(
                f"Updated PostHog properties for user {distinct_id}: {len(active_segment_names)} active segments"
            )

        except Exception as e:
            logger.error(f"Error updating PostHog properties: {str(e)}")
            raise


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
    def post(self, request: HttpRequest, topic_name: str = None):
        if not self.is_authorized:
            return JsonResponse({"message": "Authentication failed"}, status=401)

        try:
            envelope = json.loads(request.body)
            pubsub_message = envelope.get("message", {})
            message_data = pubsub_message.get("data")
            if message_data:
                decoded_data = json.loads(base64.b64decode(message_data).decode("utf-8"))
                event = IncomingEvent.of(decoded_data)

                if "external-data" in topic_name:
                    # external-data-local
                    # external-data-staging
                    # external-data-production
                    if not ExternalDataEventHandler.handle(event):
                        logger.warning(f"Event for topic {topic_name} was not handled successfully")
                        return JsonResponse({"message": "Event not handled"}, status=500)
                else:
                    logger.warning(f"Unhandled topic: {topic_name}")
                    return JsonResponse({"message": f"Unhandled topic: {topic_name}"}, status=400)

        except ValueError as ve:
            logger.warning(f"Validation error while processing message: {ve}")
            return JsonResponse({"message": str(ve)}, status=400)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return JsonResponse({"message": "Error processing message"}, status=500)

        logger.info(f"Successfully processed message for topic {topic_name}")
        return JsonResponse({"status": "OK"}, status=200)

    @staticmethod
    def is_authorized(request: HttpRequest) -> bool:
        if environment_checker.is_local() or environment_checker.is_test():
            logger.info("Authorizing as local or test execution")
            return True

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.error("Missing Authorization header")
            return False

        try:
            _, token = auth_header.split()
            id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
            )
            return True

        except Exception as e:
            logger.error(f"Invalid token: {str(e)}")
            return False
