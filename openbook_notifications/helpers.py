import logging

logger = logging.getLogger(__name__)


def flatten_payload(d, parent_key=""):
    flat_dict = {}
    for key, value in d.items():
        new_key = f"{parent_key}{key[0].upper() + key[1:]}" if parent_key else key
        if isinstance(value, dict):
            if key == "data":
                flat_dict.update(flatten_payload(value, parent_key))
            else:
                flat_dict.update(flatten_payload(value, new_key))
        else:
            flat_dict[new_key] = value
    return flat_dict


def replace_mentions_with_full_names(text, mentioned_users):
    for user in mentioned_users:
        user_id = f"@{user.username}"
        user_full_name = f"{user.profile.full_name()}"
        text = text.replace(user_id, user_full_name)
    return text
