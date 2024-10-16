import re
import secrets
from openbook_common.utils.model_loaders import get_user_invite_model, get_user_model

import logging

logger = logging.getLogger(__name__)


def update_invite(email, name=None, username=None, badge=None):
    UserInvite = get_user_invite_model()
    invites = UserInvite.objects.filter(email=email)
    if len(invites) == 2:
        invite = invites.filter(username=username).first()
        if invite is None:
            invite = invites.last()
    else:
        invite = invites.first()
    invite.username = username
    invite.save()
    logger.info("New username is: ", invite.username)
    return invite


def sanitise_username(username):
    chars = "[@#!±$%^&*()=|/><?,:;\~`{}]"
    return re.sub(chars, "", username).lower().replace(" ", "_").replace("+", "_").replace("-", "_").replace("\\", "")


def get_column_numbers_for_indiegogo(first_row):
    for index, col in enumerate(first_row):
        if col == "Name":
            name = index
        elif col == "Username":
            username = index
        elif col == "Badge Keyword":
            badge_keyword = index
        elif col == "Email":
            email = index

    return name, email, username, badge_keyword


def get_column_numbers_for_kickstarter(first_row):
    for index, col in enumerate(first_row):
        if col == "Backer Name":
            name = index
        elif (
            col == "To What Email Should We Send Your Early Access To? "
            "(Please Provide A Valid Address. We Won't Be Able To Reach Out To You If You Don't.)"
        ):
            email = index
        elif (
            col == "What @Username Would You Like To Claim/Reseve? "
            "(2 32 Characters, Letters, Numbers, Periods And Underscores)"
        ):
            username = index
        elif col == "Badge Keyword":
            badge_keyword = index
        elif col == "Email":
            email_kickstarter = index

    return name, email, username, badge_keyword, email_kickstarter


def get_column_numbers_for_conflicts_csv(first_row):
    for index, col in enumerate(first_row):
        if col == "Chosen username":
            name = index
        elif col == "Email":
            email = index

    return name, email


def get_temporary_username(email):
    username = email.split("@")[0]
    temp_username = sanitise_username(username) + str(secrets.randbelow(9999))
    User = get_user_model()
    while User.is_username_taken(temp_username):
        temp_username = username + str(secrets.randbelow(9999))

    return temp_username
