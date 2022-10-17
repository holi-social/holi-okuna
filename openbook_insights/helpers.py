import uuid
from os.path import splitext


def upload_to_insight_directory(insight, filename):
    extension = splitext(filename)[1].lower()
    new_filename = str(uuid.uuid4()) + extension

    path = f'insights/{str(insight.id)}/'

    return f'{path}{new_filename}'
