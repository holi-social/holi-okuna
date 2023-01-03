import json
import polib
import os, django
from django.conf import settings

CATEGORIES_PATH = os.path.join(settings.BASE_DIR, "openbook_common/fixtures/emoji-groups.json")
PO_LOCALES_PATH = os.path.join(settings.BASE_DIR, "locale")
FIELDS = ["keyword"]

for language in settings.LANGUAGES:
    language_code = language[0]
    if language_code == "en":
        continue
    print(f"Processing locale {language_code}")

    po_locale = polib.pofile(os.path.join(PO_LOCALES_PATH, f"{language_code}/LC_MESSAGES/django.po"))
    po_dict = {}
    for entry in po_locale:
        po_dict[entry.msgid] = entry.msgstr

    with open(CATEGORIES_PATH, "r") as f:
        emoji_dict = json.load(f)

    for emoji in emoji_dict:
        for field in FIELDS:
            field_value = emoji["fields"][f"{field}_en"]
            try:
                field_locale_value = po_dict[field_value]
                emoji["fields"][f"{field}_{language_code}"] = field_locale_value
            except KeyError:
                print(f"Field {field_value} not found in {language_code}/django.po")
        # print(emoji['fields']['description_en'])

    with open(CATEGORIES_PATH, "w") as json_file:
        json.dump(emoji_dict, json_file, ensure_ascii=False)
