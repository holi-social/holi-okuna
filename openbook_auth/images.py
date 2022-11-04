from django.core.files.storage import default_storage

image_storage = default_storage


def store_avatar(username, image_file):
    """
    stores an image as avatar. delete_old_avatars has to be called afterwards with the returned file_id as file_id_to_keep
    to clean up old avatar images for the user.
    """
    return default_storage.save(
        name=f"{username}/avatar/{username}/{image_file.name})", content=image_file
    )


def delete_avatar(url):
    """
    delete an avatar image by url
    """
    default_storage.delete(url)
