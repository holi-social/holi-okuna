from datetime import datetime
from logging import Logger

import strawberry
import structlog

from anon_stats.models import Counter

logger: Logger = structlog.get_logger(__name__)


# Create your tests here.
@strawberry.type
class Mutation:
    @strawberry.mutation()
    async def anon_count(self, counter_name: str) -> None:
        # silently ignore if no counter_name was given
        if not counter_name or counter_name.strip() == "":
            return
        # caller does not care about the result so we ignore any potential errors that could occur
        # noinspection PyAsyncCall
        try:
            await Counter.objects.acreate(name=counter_name, timestamp=datetime.now())
        except Exception as e:
            logger.warning(f"Silently ignoring exception while creating counter {e}", exc_info=True)
            pass
