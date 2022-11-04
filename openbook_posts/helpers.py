from openbook_common.helpers import create_upload_filename


def upload_to_post_directory(post, filename):
    return _upload_to_post_directory_directory(post=post, filename=filename)


def upload_to_post_image_directory(post_image, filename):
    post = post_image.post
    return _upload_to_post_directory_directory(post=post, filename=filename)


def upload_to_post_video_directory(post_video, filename):
    post = post_video.post
    return _upload_to_post_directory_directory(post=post, filename=filename)


def _upload_to_post_directory_directory(post, filename):
    return create_upload_filename(
        username=post.creator.username,
        object_type="post",
        object_id=str(post.id),
        filename=filename,
    )
