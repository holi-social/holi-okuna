import sentry_sdk
from django.core.exceptions import ValidationError
from graphql import GraphQLError
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.scrubber import EventScrubber
from sentry_sdk.integrations.strawberry import StrawberryIntegration

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


class HoliSentryTracesSampler:
    def __init__(self, default_sample_rate: float):
        self.default_sample_rate = default_sample_rate

    def traces_sampler(self, sampling_context):
        for key, value in sampling_context["asgi_scope"]["headers"]:
            if key == b"x-disable-sentry" and value == b"true":
                return 0

        # always inherit
        if sampling_context["parent_sampled"] is not None:
            return sampling_context["parent_sampled"]

        return self.default_sample_rate


def init(sentry_dsn: str, sample_rate: float, environment: str) -> None:
    if not sentry_dsn:
        raise NameError(f"Sentry DSN is required for {environment}")

    sampler = HoliSentryTracesSampler(sample_rate)
    sentry_sdk.init(
        dsn=sentry_dsn,
        event_scrubber=EventScrubber(),  # Remove PII
        integrations=[DjangoIntegration(), StrawberryIntegration(async_execution=True)],
        before_send=sentry_event_processor,
        traces_sampler=sampler.traces_sampler,
        environment=environment,
    )
