from openbook_common.helpers import create_upload_filename


def upload_to_insight_directory(insight, filename):
    return create_upload_filename(
        username=insight.creator.username,
        object_type="insight",
        object_id=str(insight.id),
        filename=filename,
    )
