# ruff: noqa
import tempfile
from json import dumps
from urllib.parse import urlparse

import blurhash
import requests
import strawberry
from django.conf import settings
from django.db.models import Q
from langdetect import DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from PIL import ExifTags, Image
from PIL.Image import Transpose
from urlextract import URLExtract

from openbook.settings import ALERT_HOOK_URL
from openbook_common.utils.model_loaders import get_language_model
from openbook_translation import translation_strategy

# seed the language detector
DetectorFactory.seed = 0


def get_detected_language_code(text):
    try:
        detected_lang = translation_strategy.get_detected_language_code(text)
    except LangDetectException:
        detected_lang = None
    return detected_lang


def get_language_for_text(text):
    language_code = get_detected_language_code(text)
    Language = get_language_model()
    if language_code is not None and Language.objects.filter(code=language_code).exists():
        return Language.objects.get(code=language_code)

    return None


def get_supported_translation_language(language_code):
    Language = get_language_model()
    supported_translation_code = translation_strategy.get_supported_translation_language_code(language_code)

    return Language.objects.get(code=supported_translation_code)


extractor = URLExtract()


def extract_urls_from_string(text):
    """
    Returns all the raw extracted urls as a list
    If a URL has a scheme, it ensures that it is http/s
    URLs like www. are sanitised in the normalise_url
    """
    results = list(extractor.gen_urls(text))
    for url in results:
        scheme = urlparse(url).scheme
        if scheme and scheme != "https" and scheme != "http":
            results.remove(url)

    return results


def make_proxy_image_url(image_url):
    proxy_image_url = settings.PROXY_URL + image_url

    return proxy_image_url


def write_in_memory_file_to_disk(in_memory_file):
    # Write it to disk
    tmp_file = tempfile.mkstemp(suffix=in_memory_file.name)
    tmp_file_path = tmp_file[1]
    tmp_file = open(tmp_file_path, "wb")
    tmp_file.write(in_memory_file.read())
    tmp_file.seek(0)
    tmp_file.close()
    return tmp_file


def send_alert_to_channel(alert):
    post = {"text": alert}

    json_data = dumps(post)
    response = requests.post(
        ALERT_HOOK_URL,
        data=json_data.encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    if response.status_code != requests.status_codes.codes.ok:
        raise ValueError(f"{response.status_code} != 200")


def create_upload_filename(object_type, object_id, filename, username=None):
    if username is None:
        return f"{object_type}/{object_id}/{filename}"

    return f"{object_type}/{object_id}/{filename}/{username}"


def attr_filled(obj, attr):
    return bool(getattr(obj, attr, None))


def is_parameter_null(obj, attr):
    return attr in obj and obj[attr] is None


def prefix_keys(kwargs, prefix):
    if prefix:
        return {prefix + "__" + key.lstrip("_"): value for key, value in kwargs.items()}
    return {"id" + key if key.startswith("_") else key: value for key, value in kwargs.items()}


def PQ(prefix=None, **kwargs):
    return Q(**prefix_keys(kwargs, prefix))


class PrefixedQ:
    def __init__(self, prefix=None):
        self.prefix = prefix

    def __call__(self, **kwargs):
        return Q(**prefix_keys(kwargs, self.prefix))

    def prefix_plus(self, prefix=None):
        if self.prefix:
            return self.prefix + "__" + prefix.lstrip("_")
        return prefix


class ExifRotate:
    def process(self, img):
        exif = img.getexif()
        if not exif or ExifTags.Base.Orientation not in exif:
            return img

        orientation = exif[ExifTags.Base.Orientation]
        match orientation:
            case 2:
                return img.transpose(Transpose.FLIP_LEFT_RIGHT)
            case 3:
                return img.transpose(Transpose.ROTATE_180)
            case 4:
                return img.transpose(Transpose.FLIP_TOP_BOTTOM)
            case 5:
                return img.transpose(Transpose.ROTATE_270).transpose(Transpose.FLIP_LEFT_RIGHT)
            case 6:
                return img.transpose(Transpose.ROTATE_270)
            case 7:
                return img.transpose(Transpose.ROTATE_90).transpose(Transpose.FLIP_LEFT_RIGHT)
            case 8:
                return img.transpose(Transpose.ROTATE_90)
            case _:
                return img


def generate_blurhash(obj) -> str | None:
    if obj is None:
        return None
    with Image.open(obj).convert("RGB") as img:
        return blurhash.encode(img, x_components=4, y_components=3)


def to_input_dict(input):
    """
    converts a strawberry input object to a dict without null values, so it can be validated
    """
    return {k: v for k, v in strawberry.asdict(input).items() if v != strawberry.UNSET}
