from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework import authentication

from rest_framework import exceptions

from django.utils.translation import gettext_lazy as _

HEADER_USER_ID = 'X-Holi-User-ID'
HEADER_USER_EMAIL = 'X-Holi-User-Email'


class HoliOathkeeperAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        # in "production" request headers show up in `request.headers`, in unit testing they show up in `request.META`
        user_id = request.headers.get(HEADER_USER_ID, request.META.get(HEADER_USER_ID))
        user_email = request.headers.get(HEADER_USER_EMAIL, request.META.get(HEADER_USER_EMAIL))

        print("==> user_id %s" % user_id)
        print("==> user_email %s" % user_email)

        if user_id == 'anonymous':
            print("==> anonymous login")
            return AnonymousUser(), None

        if not user_id:
            print("==> missing user_id")
            return None

        with transaction.atomic():
            try:
                User = get_user_model()
                user = self.get_user(user_id)
                print("==> found user %s" % user)
            except User.DoesNotExist:
                if not user_email:
                    return None
                user = User.create_user(username=user_id, email=user_email, is_of_legal_age=True,
                                        are_guidelines_accepted=True)
                print("==> created user %s" % user)

        if not user.is_active:
            msg = _('User account is disabled.')
            print("==> user is inactive %s" % user)
            raise exceptions.AuthenticationFailed(msg)

        print("==> returning user %s" % user)
        return user, None

    def get_user(self, user_id):
        User = get_user_model()
        return User.objects.get_by_natural_key(user_id)
