import uuid
from os.path import splitext


def upload_to_insight_directory(insight, filename):
    extension = splitext(filename)[1].lower()
    new_filename = str(uuid.uuid4()) + extension

    path = 'insights/%(insight_id)s/' % {
        'insight_id': str(insight.id)}

    return '%(path)s%(new_filename)s' % {'path': path,
                                         'new_filename': new_filename, }
