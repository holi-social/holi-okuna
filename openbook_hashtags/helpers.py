from openbook_common.helpers import create_upload_filename


def upload_to_hashtags_directory(hashtag, filename):
    return create_upload_filename(object_type="hashtag", object_id=hashtag.id, filename=filename)
