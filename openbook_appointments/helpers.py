from openbook_common.helpers import create_upload_filename


def upload_to_space_appointment_thumbnail_directory(appointment, filename):
    return create_upload_filename(
        username=appointment.space.creator.username,
        object_type="space_appointment_thumbnail",
        object_id=appointment.space.id,
        filename=filename,
    )
