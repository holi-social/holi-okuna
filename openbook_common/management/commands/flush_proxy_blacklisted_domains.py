from django.core.management.base import BaseCommand

from openbook_common.models import ProxyBlacklistedDomain

import logging
from django.core.validators import URLValidator

logger = logging.getLogger(__name__)

url_validator = URLValidator()


class Command(BaseCommand):
    help = "Flush all of the proxy blacklisted domains"

    def handle(self, *args, **options):
        ProxyBlacklistedDomain.objects.all().delete()
