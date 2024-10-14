import json
import polib
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

MODERATION_CATEGORIES_PATH = os.path.join(settings.BASE_DIR, "openbook_moderation/fixtures/moderation_categories.json")
PO_LOCALES_PATH = os.path.join(settings.BASE_DIR, "locale")
FIELDS = ["title", "description"]

for language in settings.LANGUAGES:
    language_code = language[0]
    if language_code == "en":
        continue
    logger.debug(f"Processing locale {language_code}")

    po_locale = polib.pofile(os.path.join(PO_LOCALES_PATH, f"{language_code}/LC_MESSAGES/django.po"))
    po_dict = {}
    for entry in po_locale:
        po_dict[entry.msgid] = entry.msgstr

    with open(MODERATION_CATEGORIES_PATH, "r") as f:
        categories_dict = json.load(f)

    for category in categories_dict:
        for field in FIELDS:
            field_value = category["fields"][f"{field}_en"]
            try:
                field_locale_value = po_dict[field_value]
                category["fields"][f"{field}_{language_code}"] = field_locale_value
            except KeyError:
                logger.debug(f"Field {field_value} not found in {language_code}/django.po")

    with open(MODERATION_CATEGORIES_PATH, "w") as json_file:
        json.dump(categories_dict, json_file, ensure_ascii=False)
