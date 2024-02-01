from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound

from openbook_appointments.services import AppointmentService


def space_member_exists(username):
    from openbook_auth.models import User

    if not User.user_with_username_exists(username=username):
        raise NotFound(_(f"Space member with username {username} not found"))


def appointment_exists(appointment_id):
    if not AppointmentService().exists(appointment_id=appointment_id):
        raise NotFound(_(f"Appointment with id {appointment_id} not found"))
