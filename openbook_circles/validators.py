from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from openbook_circles.models import Circle


def circle_id_exists(circle_id):
    if not Circle.objects.filter(id=circle_id).exists():
        raise ValidationError(
            _("The circle does not exist."),
        )
