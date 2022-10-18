from django.core.files.storage import default_storage

image_storage = default_storage


def store_avatar(username, image_file):
    """
    stores an image as avatar. delete_old_avatars has to be called afterwards with the returned file_id as file_id_to_keep
    to clean up old avatar images for the user.
    """
    return default_storage.save(
        name=f"{username}/avatar/{username}/{image_file.name})",
        content=image_file)
                  file_id_to_keep=file_id_to_keep)
        file=image_file, file_name=file_name, options=options)
        {"tags": "user_" + authenticated_user.username, "path": folder})


def delete_avatar(url):
    """
    delete an avatar image by url
    """
    default_storage.delete(url)
                f"Could not delete image file with fileId: {file_id}. Error response: {error}")
            f"Could not delete image file with fileId: {file_id}.", exc_info=True)
