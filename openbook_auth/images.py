from imagekitio.client import ImageKit
from requests import RequestException

from openbook.settings import IMAGEKIT_PUBLIC_KEY, IMAGEKIT_PRIVATE_KEY, IMAGEKIT_URL
import os
import logging

logger = logging.getLogger(__name__)


def store_avatar(authenticated_user, image_file):
    """
    stores an image as avatar. delete_old_avatars has to be called afterwards with the returned file_id as file_id_to_keep
    to clean up old avatar images for the user.
    """
    return store_image(authenticated_user, image_file, 'avatars', ['avatar'])


def delete_old_avatars(authenticated_user, file_id_to_keep):
    """
    Needs to be called after store_avatar to remove old and obsolete avatar images
    """
    delete_images(authenticated_user, folder="avatars",
                  file_id_to_keep=file_id_to_keep)


def store_image(authenticated_user, image_file, folder=None, tags=[]):
    """
    Store an image in our image service and return the file_id and rendered URL
    Given Tags are added to the image. user_id is always added as an additional tag
    """
    _add_user(authenticated_user, tags)
    options = {"tags": tags}
    if folder is not None:
        options['folder'] = folder
    imagekit = _get_imagekit()
    file_name = _create_avatar_file_name(authenticated_user, image_file)
    upload = imagekit.upload(
        file=image_file, file_name=file_name, options=options)
    response = upload['response']
    return response['fileId'], response['url']


def delete_images(authenticated_user, folder=None, file_id_to_keep=''):
    """
    Delete all images that have the given tags, except the one that is passed as file_id_to_keep
    """
    imagekit = _get_imagekit()
    old_files = imagekit.list_files(
        {"tags": "user_" + authenticated_user.username, "path": folder})
    for file in old_files['response']:
        file_id = file['fileId']
        if file_id != file_id_to_keep:
            delete_image(file_id, imagekit)


def delete_image(file_id, imagekit):
    """
    delete an image by file_id
    """
    if imagekit is None:
        imagekit = _get_imagekit()
    try:
        error = imagekit.delete_file(file_id).get('error')
        if error is not None:
            logger.warning(
                f"Could not delete image file with fileId: {file_id}. Error response: {error}")
    except RequestException:
        logger.warning(
            f"Could not delete image file with fileId: {file_id}.", exc_info=True)


def _add_user(authenticated_user, tags):
    tags.append("user_" + authenticated_user.username)


def _get_imagekit():
    return ImageKit(
        private_key=IMAGEKIT_PRIVATE_KEY,
        public_key=IMAGEKIT_PUBLIC_KEY,
        url_endpoint=IMAGEKIT_URL,
    )


def _create_avatar_file_name(authenticated_user, image_file):
    _, file_extension = os.path.splitext(image_file.name)
    return authenticated_user.username + file_extension
