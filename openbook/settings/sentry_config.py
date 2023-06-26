import sentry_sdk
from django.core.exceptions import ValidationError
from graphql import GraphQLError
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.rq import RqIntegration
from sentry_sdk.scrubber import EventScrubber

from openbook.graphql_errors import GraphQLErrorCodes


def sentry_event_processor(event, hint):
    if "exc_info" not in hint:
        return event

    exception = hint["exc_info"][1]
    if isinstance(exception, ValidationError):
        return None
    if isinstance(exception, GraphQLError) and exception.extensions["code"] in [
        GraphQLErrorCodes.NOT_FOUND,
        GraphQLErrorCodes.UNAUTHORIZED,
        GraphQLErrorCodes.FORBIDDEN,
        GraphQLErrorCodes.BAD_USER_INPUT,
    ]:
        return None

    return event


def init(sentry_dsn: str, sample_rate: float, environment: str) -> None:
    if not sentry_dsn:
        raise NameError(f"Sentry DSN is required for {environment}")
    sentry_sdk.init(
        dsn=sentry_dsn,
        event_scrubber=EventScrubber(),  # Remove PII
        integrations=[DjangoIntegration(), RqIntegration()],
        before_send=sentry_event_processor,
        traces_sample_rate=sample_rate,  # Only sample 5% of requests in prod, all in staging
        environment=environment,
    )
