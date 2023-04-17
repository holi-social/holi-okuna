from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils.translation import gettext_lazy as _
from openbook import settings

from openbook_common.helpers import extract_urls_from_string
from openbook_common.utils.model_loaders import get_proxy_blacklist_domain_model

from google.cloud.webrisk_v1 import WebRiskServiceClient, SearchUrisRequest, ThreatType
import structlog

logger = structlog.getLogger(__name__)

ENVIRONMENT_ID = settings.ENVIRONMENT_ID

# This check is used on nginx auth, doesn't support 400
def check_url_can_be_proxied(url):
    urls = extract_urls_from_string(url)

    if not urls:
        raise PermissionDenied(
            _("No valid URL given"),
        )

    ProxyBlacklistDomain = get_proxy_blacklist_domain_model()
    if ProxyBlacklistDomain.is_url_domain_blacklisted(url):
        raise PermissionDenied(
            _("Url is blacklisted"),
        )


def check_url_safety(url: str):
    if ENVIRONMENT_ID == "local":
        return

    webrisk_client = WebRiskServiceClient()

    request = SearchUrisRequest()
    request.uri = url
    request.threat_types = [
        ThreatType.MALWARE,
        ThreatType.SOCIAL_ENGINEERING,
        ThreatType.SOCIAL_ENGINEERING_EXTENDED_COVERAGE,
        ThreatType.UNWANTED_SOFTWARE,
    ]

    response = webrisk_client.search_uris(request)
    threat_types = response.threat.threat_types

    if threat_types:
        logger.debug(f"The URL has the following threat types: {threat_types}")
        raise ValidationError(
            _("The link cannot be posted as it was detected as malicious"),
        )
