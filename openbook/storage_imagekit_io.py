import logging
import os
import urllib3

from django.core.files.base import ContentFile
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
        self.http = urllib3.PoolManager()

    def delete(self, name):
        self.delete_image(self._get_file_id(name))

    def exists(self, name):
        return False

    def url(self, name):
        return name

    def _open(self, name, mode="rb"):
        return ContentFile(self.http.request("GET", name).data)

    def _save(self, name, content):
        if name.count("/") < 2:
            raise IncorrectFilename(
                "Filenames need to have at least three sections: object_type/object_id/filename.ext[/username] but filename was: "
                + name
            )
        split = name.split("/")
        object_type = split[0]
        object_id = split[1]
        filename = split[2]

        type_tag = f"{object_type}_{object_id}"
        tags = [type_tag]
        if len(split) > 3:
            tags.append(f"user_{split[3]}")
        old_files = self.imagekit.list_files({"tags": type_tag, "path": object_type})

        options = {"folder": object_type, "tags": tags}
        content.name = object_id + _get_file_extension(filename)
        upload = self.imagekit.upload(
            file=content, file_name=content.name, options=options
        )

        if old_files and old_files["response"]:
            self.delete_images(map(lambda file: file["fileId"], old_files["response"]))
            logger.info(
                "deleted %s old versions of the file", len(old_files["response"])
            )

        # once, the container did not start because part of the return statement was None. Therefore I integrated logging for analysis next time around.
        logger.info("UPLOAD result: %s", upload)
        return upload["response"]["url"]

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
            error = self.imagekit.delete_file(file_id).get("error")
            if error is not None:
                logger.warning(
                    "Could not delete image file with fileId: %s. Error response: %s",
                    file_id,
                    error,
                )
        except RequestException:
            logger.warning(
                "Could not delete image file with fileId: %s.", file_id, exc_info=True
            )

    def _get_file_id(self, url):
        filename = os.path.basename(url)
        return self.imagekit.list_files({"name": filename})["response"][0]["fileId"]


def _get_file_extension(filename):
    return os.path.splitext(filename)[1].lower()
