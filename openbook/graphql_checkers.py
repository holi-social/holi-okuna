from graphql import GraphQLError
from openbook import settings

from google.cloud.webrisk_v1 import WebRiskServiceClient, SearchUrisRequest, ThreatType
import structlog

from openbook.graphql_errors import GraphQLErrorCodes

logger = structlog.getLogger(__name__)

ENVIRONMENT_ID = settings.ENVIRONMENT_ID


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
        logger.debug(f"The link has the following threat types: {threat_types}")
        raise GraphQLError(
            "The link cannot be posted as it was detected as malicious",
            extensions={"code": GraphQLErrorCodes.BAD_USER_INPUT, "field": "url"},
        )
