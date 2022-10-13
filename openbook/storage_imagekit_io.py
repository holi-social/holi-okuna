import logging
import os

from django.core.files.storage import Storage
from imagekitio import ImageKit
from requests import RequestException

from openbook import settings

logger = logging.getLogger(__name__)


class IncorrectFilename(Exception):
    pass


class ImagekitIoStorage(Storage):

    def __init__(self):
        self.imagekit = ImageKit(
            private_key=settings.IMAGEKIT_PRIVATE_KEY,
            public_key=settings.IMAGEKIT_PUBLIC_KEY,
            url_endpoint=settings.IMAGEKIT_URL,
        )

    def delete(self, name):
        self.delete_image(self._get_file_id(name))

    def exists(self, name):
        return False

    def url(self, name):
        return name

    def _open(self, name, mode='rb'):
        raise NotImplementedError(
            "ImagekitIoStorage does not support opening of images"
        )

    def _save(self, name, content):
        if name.count("/") != 3:
            raise IncorrectFilename(
                "Filenames need to have four sections: username/object_type/object_id/filename.ext but filename was: " + name)
        username, object_type, object_id, filename = name.split("/")

        type_tag = "%s_%s" % (object_type, object_id)
        old_files = self.imagekit.list_files({"tags": type_tag, "path": object_type})

        options = {
            "folder": object_type,
            "tags": ["user_%s" % username, type_tag]
        }
        content.name = object_id + _get_file_extension(filename)
        upload = self.imagekit.upload(file=content, file_name=content.name, options=options)

        self.delete_images(map(lambda file: file['fileId'], old_files['response']))

        return upload['response']['url']

    def delete_images(self, file_ids):
        """
        Delete files given a list of file_ids.
        """
        for file_id in file_ids:
            self.delete_image(file_id)

    def delete_image(self, file_id):
        """
        Delete an image by file_id
        """
        try:
            error = self.imagekit.delete_file(file_id).get('error')
            if error is not None:
                logger.warning("Could not delete image file with fileId: %s. Error response: %s", file_id, error)
        except RequestException:
            logger.warning("Could not delete image file with fileId: %s.", file_id, exc_info=True)

    def _get_file_id(self, url):
        filename = os.path.basename(url)
        return self.imagekit.list_files({"name": filename})['response'][0]['fileId']


def _get_file_extension(filename):
    return os.path.splitext(filename)[1].lower()
