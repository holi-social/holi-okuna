from openbook_common.helpers import create_upload_filename


# This function is deprecated. Please use the new upload_to_new_feed_post_images_directory function instead. Remove
# it after version 1.30.x
def upload_to_feed_post_images_directory(post, filename: str):
    return create_upload_filename(
        username=post.creator.username,
        object_type="feed_post_image",
        object_id=post.id,
        filename=filename,
    )


def upload_to_new_feed_post_images_directory(instance, filename: str):
    return create_upload_filename(
        username=instance.feed_post.creator.username,
        object_type="feed_post_image",
        object_id=instance.feed_post.id,
        filename=filename,
    )
