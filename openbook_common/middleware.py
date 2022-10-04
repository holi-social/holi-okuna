import pytz
import logging

from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class TimezoneMiddleware(MiddlewareMixin):
    """
    A middleware to activate the user timezone if it has been stored in the session.
    """

    def process_request(self, request):
        tzname = request.META.get('HTTP_TIME_ZONE')
        if tzname:
            timezone.activate(pytz.timezone(tzname))
        else:
            timezone.deactivate()


class ChunkedContentLengthMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.META.get("HTTP_TRANSFER_ENCODING") == "chunked":
            request.META["CONTENT_LENGTH"] = len(request.body)
        return None
