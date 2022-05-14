import jwt

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework import exceptions

from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from rest_framework_jwt.blacklist.exceptions import MissingToken
from rest_framework_jwt.compat import ExpiredSignature
from rest_framework_jwt.compat import gettext_lazy as _


class HoliJsonWebTokenAuthentication(JSONWebTokenAuthentication):

    # overrides JSONWebTokenAuthentication.authenticate to allow creating users that don't exist yet
    def authenticate(self, request):
        try:
            token = self.get_token_from_request(request)
            if token is None:
                return None
        except MissingToken:
            return None

        try:
            payload = self.jwt_decode_token(token)
        except ExpiredSignature:
            msg = _('Token has expired.')
            raise exceptions.AuthenticationFailed(msg)
        except jwt.DecodeError:
            msg = _('Error decoding token.')
            raise exceptions.AuthenticationFailed(msg)
        except jwt.InvalidTokenError:
            msg = _('Invalid token.')
            raise exceptions.AuthenticationFailed(msg)

        if apps.is_installed('rest_framework_jwt.blacklist'):
            from rest_framework_jwt.blacklist.models import BlacklistedToken
            if BlacklistedToken.is_blocked(token, payload):
                msg = _('Token is blacklisted.')
                raise exceptions.PermissionDenied(msg)

        username = payload.get('sub')
        email = payload.get('email')

        print(f"payload=%s", payload)
        print(f"username=%s, email=%s", username, email)

        if not username:
            msg = _('Invalid payload.')
            raise exceptions.AuthenticationFailed(msg)

        with transaction.atomic():
            User = get_user_model()
            try:
                user = User.objects.get_by_natural_key(username)
            except User.DoesNotExist:
                user = User.create_user(username=username, email=email, is_of_legal_age=True,
                                        are_guidelines_accepted=True)

        if not user.is_active:
            msg = _('User account is disabled.')
            raise exceptions.AuthenticationFailed(msg)

        return user, token
