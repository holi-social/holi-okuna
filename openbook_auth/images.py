from imagekitio.client import ImageKit
from openbook.settings import IMAGEKIT_PUBLIC_KEY, IMAGEKIT_PRIVATE_KEY, IMAGEKIT_URL
import os


def get_avatar_url(authenticated_user, image_file):
    file_name = create_avatar_file_name(authenticated_user, image_file)
    return get_imagekit().url(options={'path': '/avatars/' + file_name})


def store_avatar(authenticated_user, image_file):
    file_name = create_avatar_file_name(authenticated_user, image_file)
    return store_image(image_file, file_name, 'avatars', ['avatar'])


def store_image(image_file, file_name, folder=None, tags=None):
    """Store an image in our image service and return the rendered URL"""

    # options = {"use_unique_file_name": False}
    if tags is None:
        tags = []
    tags.append(file_name)
    options = {"tags": tags}
    if folder is not None:
        options['folder'] = folder
    imagekit = get_imagekit()
    old_files = imagekit.list_files({"tags": ','.join(tags)})
    for file in old_files['response']:
        imagekit.delete_file(file['fileId'])
    upload = imagekit.upload(file=image_file, file_name=file_name, options=options)
    url = upload['response']['url']
    return url


def get_imagekit():
    return ImageKit(
        private_key=IMAGEKIT_PRIVATE_KEY,
        public_key=IMAGEKIT_PUBLIC_KEY,
        url_endpoint=IMAGEKIT_URL,
    )


def create_avatar_file_name(authenticated_user, image_file):
    _, file_extension = os.path.splitext(image_file.name)
    return authenticated_user.username + file_extension
