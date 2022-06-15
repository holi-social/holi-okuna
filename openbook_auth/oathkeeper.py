from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.backends import BaseBackend

from rest_framework import exceptions

from django.utils.translation import gettext_lazy as _


class HoliOathkeeperAuthentication(BaseBackend):
    def authenticate(self, request, **kwargs):
        user_id = request.headers.get('X-Holi-User-ID')
        user_email = request.headers.get('X-Holi-User-Email')

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
