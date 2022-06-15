from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework import authentication

from rest_framework import exceptions

from django.utils.translation import gettext_lazy as _


class HoliOathkeeperAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        user_id = request.headers.get('X-Holi-User-ID')
        user_email = request.headers.get('X-Holi-User-Email')

        if user_id == 'anonymous':
            return AnonymousUser(), None

        if not user_id:
            return None

        with transaction.atomic():
            try:
                User = get_user_model()
                user = self.get_user(user_id)
            except User.DoesNotExist:
                if not user_email:
                    return None
                user = User.create_user(username=user_id, email=user_email, is_of_legal_age=True,
                                        are_guidelines_accepted=True)

        if not user.is_active:
            msg = _('User account is disabled.')
            raise exceptions.AuthenticationFailed(msg)

        return user, None

    def get_user(self, user_id):
        User = get_user_model()
        return User.objects.get_by_natural_key(user_id)
