from openbook_common.helpers import create_upload_filename


def upload_to_feed_post_images_directory(post, filename: str):
    return create_upload_filename(
        username=post.creator.username,
        object_type="feed_post_image",
        object_id=post.id,
        filename=filename,
    )
