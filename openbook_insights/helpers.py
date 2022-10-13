import uuid
from os.path import splitext


def upload_to_insight_directory(insight, filename):
    return 'admin/insight/%(id)s/%(filename)s' % {
        'id': str(insight.id),
        'filename': filename,
    }
