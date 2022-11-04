from openbook_common.helpers import create_upload_filename

def upload_to_spaces_main_image_directory(space, filename):
    return create_upload_filename(username=space.creator.username,
                                  object_type="space_main_image",
                                  object_id=space.id,
                                  filename=filename)
