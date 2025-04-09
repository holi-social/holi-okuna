import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions

from openbook_auth.tasks import extend_ory_session, generate_identity_when_needed, get_oidc

CACHE_TIMEOUT = 300

HEADER_USER_ID = "X-Holi-User-ID"
HEADER_USER_EMAIL = "X-Holi-User-Email"
HEADER_USER_GIVEN_NAME = "X-Holi-User-given_name"
HEADER_USER_FAMILY_NAME = "X-Holi-User-family_name"
HEADER_SESSION = "X-Holi-Session"
HEADER_SESSION_EXPIRY = "X-Holi-Session-Expiry"

logger = logging.getLogger("openbook_auth/oathkeeper")


class HoliOathkeeperAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        # in "production" request headers show up in `request.headers`, in unit testing they show up in `request.META`
        user_id = request.headers.get(HEADER_USER_ID, request.META.get(HEADER_USER_ID))
        user_email = request.headers.get(HEADER_USER_EMAIL, request.META.get(HEADER_USER_EMAIL))
        user_session = request.headers.get(HEADER_SESSION, request.META.get(HEADER_SESSION))
        user_session_expiry = request.headers.get(HEADER_SESSION_EXPIRY, request.META.get(HEADER_SESSION_EXPIRY))
        extend_ory_session(user_session, user_session_expiry)

        if user_id == "anonymous":
            return AnonymousUser(), None

        if not user_id:
            return None

        cache_key = settings.USER_CACHE_PREFIX + user_id
        user = cache.get(cache_key)

        if user is None:
            retry_get = False
            with transaction.atomic():
                User = get_user_model()
                try:
                    user = self._get_user(user_id)
                    cache.set(cache_key, user, timeout=CACHE_TIMEOUT)
                except User.DoesNotExist:
                    if not user_email:
                        return None
                    try:
                        is_oidc = get_oidc(user_id)
                        user_given_name = None
                        user_family_name = None
                        if is_oidc:
                            user_given_name = request.headers.get(
                                HEADER_USER_GIVEN_NAME, request.META.get(HEADER_USER_GIVEN_NAME)
                            )
                            user_family_name = request.headers.get(
                                HEADER_USER_FAMILY_NAME, request.META.get(HEADER_USER_FAMILY_NAME)
                            )
                        user = User.create_user(
                            username=user_id,
                            email=user_email,
                            is_of_legal_age=True,
                            are_guidelines_accepted=True,
                            is_oidc=is_oidc,
                            name=user_given_name,
                            last_name=user_family_name,
                        )
                        generate_identity_when_needed(user)
                        cache.set(cache_key, user, timeout=CACHE_TIMEOUT)
                    except Exception as ex:
                        logger.info(
                            "Could not create user with id %s. Parallel creation? Retrying get. Exception: %s",
                            user_id,
                            ex,
                        )
                        retry_get = True  # retry needs to be done outside the broken transaction
            if retry_get:
                try:
                    user = cache.get_or_set(cache_key, default=lambda: self._get_user(user_id), timeout=CACHE_TIMEOUT)
                except User.DoesNotExist:
                    logger.exception("Could not create user with id %s. Retrying get failed. Failing finally", user_id)
                    # when we can't create the user, the app stays most functional if we just continue anonymously
                    return AnonymousUser(), None

        if not user.is_active:
            raise exceptions.AuthenticationFailed(_("User account is disabled."))
        return user, None

    def _get_user(self, user_id):
        User = get_user_model()
        return User.objects.get_by_natural_key(user_id)
