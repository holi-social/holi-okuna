from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from openbook_lists.models import List


def list_id_exists(list_id):
    if not List.objects.filter(id=list_id).exists():
        raise ValidationError(
            _("The list does not exist."),
        )
