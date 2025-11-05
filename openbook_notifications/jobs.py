import logging
import uuid

from datetime import timedelta, datetime, time, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.utils import timezone

from openbook_common.utils.model_loaders import (
    get_user_model,
)
from openbook_notifications.services import NotificationsService


logger = logging.getLogger(__name__)


def send_pre_good_deed_email_series_to_eligible_users() -> str:
    """
    Runs daily to notify users who joined yesterday and have not yet:
      - created any feed post with category slug "good-deed"
      - committed to any volunteering opportunity
    """

    User = get_user_model()

    # Determine local-time window for "yesterday"
    local_tz = ZoneInfo("Europe/Berlin")
    yesterday = timezone.localdate() - timedelta(days=1)
    start_local = datetime.combine(yesterday, time.min)
    end_local = start_local + timedelta(days=1)
    start_aware_local = timezone.make_aware(start_local, local_tz)
    end_aware_local = timezone.make_aware(end_local, local_tz)
    start_utc = start_aware_local.astimezone(dt_timezone.utc)
    end_utc = end_aware_local.astimezone(dt_timezone.utc)

    # Users who joined yesterday
    base_qs = User.objects.filter(date_joined__gte=start_utc, date_joined__lt=end_utc)

    # Exclude users who already created a good deed
    eligible_users_qs = (
        base_qs.exclude(created_feed_posts__category__slug="good-deed")
        .exclude(volunteeringopportunitystatus__isnull=False)
        .exclude(completed_tasks__isnull=False)
        .distinct()
    )

    notified_count = 0

    for user in eligible_users_qs.iterator():
        try:
            token = str(uuid.uuid4())
            NotificationsService.send_pre_good_deed_email_series_notification(user=user, token=token)
            notified_count += 1
        except Exception:
            logger.exception("Failed to send pre-good-deed email series notification", extra={"user_id": str(user.id)})

    msg = (
        "Sent pre-good-deed email series to "
        f"{notified_count} users (joined between {start_aware_local.isoformat()} and {end_aware_local.isoformat()} local)"
    )
    logger.info(msg)
    return msg
