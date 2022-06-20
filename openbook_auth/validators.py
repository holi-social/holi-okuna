import json
import re
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError, NotFound

from openbook import settings
from openbook_auth.models import User


def username_characters_validator(username):
    if not re.match('^[a-zA-Z0-9_.-]*$', username):
        raise ValidationError(
            _('Usernames can only contain alphanumeric characters, periods and underscores.'),
        )


def username_not_taken_validator(username):
    if User.is_username_taken(username):
        raise ValidationError(
            _('The username is already taken.'),
        )


def email_not_taken_validator(email):
    if User.is_email_taken(email):
        raise ValidationError(
            _('An account for the email already exists.'),
        )


def user_username_exists(username):
    if not User.user_with_username_exists(username=username):
        raise NotFound(
            _('No user with the provided username exists.'),
        )


def user_email_exists(email):
    if not User.objects.filter(email=email).exists():
        raise NotFound(
            _('No user with the provided email exists.'),
        )


def interests_json_validator(interests):
    if type(interests) is not list:
        raise ValidationError(_('User interests must be a valid JSON list'))
    for interest in interests:
        if type(interest) is not str:
            raise ValidationError(_('User interests must be strings'))
        if len(interest) > settings.PROFILE_INTEREST_MAX_LENGTH:
            raise ValidationError(
                _("User interests may not be more than %s characters long" % settings.PROFILE_INTEREST_MAX_LENGTH))


def sdgs_json_validator(sdgs):
    if type(sdgs) is not list:
        raise ValidationError(_('User SDGs must be a valid JSON list'))
    for sdg in sdgs:
        if type(sdg) is not str:
            raise ValidationError(_('User SDGs must be strings'))
        if len(sdg) > settings.PROFILE_SDG_MAX_LENGTH:
            raise ValidationError(
                _("User SDGs may not be more than %s characters long" % settings.PROFILE_SDG_MAX_LENGTH))


def skills_json_validator(skills):
    if type(skills) is not list:
        raise ValidationError(_('User skills must be a valid JSON array'))
    for skill in skills:
        if type(skill) is not str:
            raise ValidationError(_('User skills must be strings'))
        if len(skill) > settings.PROFILE_SDG_MAX_LENGTH:
            raise ValidationError(
                _("User skills may not be more than %s characters long" % settings.PROFILE_SDG_MAX_LENGTH))
