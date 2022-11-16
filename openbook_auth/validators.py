import json
import re
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError, NotFound

from openbook import settings
from openbook_auth.models import User
from openbook_terms.models import Topic, SDG, Skill


def username_characters_validator(username):
    if not re.match("^[a-zA-Z0-9_.-]*$", username):
        raise ValidationError(
            _(
                "Usernames can only contain alphanumeric characters, periods, underscores and dashes."
            ),
        )


def username_not_taken_validator(username):
    if User.is_username_taken(username):
        raise ValidationError(
            _("The username is already taken."),
        )


def email_not_taken_validator(email):
    if User.is_email_taken(email):
        raise ValidationError(
            _("An account for the email already exists."),
        )


def user_username_exists(username):
    if not User.user_with_username_exists(username=username):
        raise NotFound(
            _("No user with the provided username exists."),
        )


def user_email_exists(email):
    if not User.objects.filter(email=email).exists():
        raise NotFound(
            _("No user with the provided email exists."),
        )


def interests_json_validator(interest_uuid):
    if not Topic.objects.filter(id=interest_uuid).exists():
        raise NotFound(
            _("Unknown UUID '" + interest_uuid + "' contained in interests array")
        )


def sdgs_json_validator(sdg_uuid):
    if not SDG.objects.filter(id=sdg_uuid).exists():
        raise NotFound(_("Unknown UUID '" + sdg_uuid + "' contained in sdgs array"))


def skills_json_validator(skill_uuid):
    if not Skill.objects.filter(id=skill_uuid).exists():
        raise NotFound(_("Unknown UUID '" + skill_uuid + "' contained in skills array"))
