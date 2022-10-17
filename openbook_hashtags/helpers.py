import uuid
from os.path import splitext


def upload_to_hashtags_directory(hashtag, filename):
    extension = splitext(filename)[1].lower()
    new_filename = str(uuid.uuid4()) + extension

    path = f'hashtags/{hashtag.name}/'

    return f'{path}{new_filename}'
