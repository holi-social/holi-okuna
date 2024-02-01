from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from openbook_appointments.models import Appointment


@admin.register(Appointment)
class AppointmentAdminModel(admin.ModelAdmin):
    model = Appointment

    @admin.display(description="Space")
    def space_name(self, obj: Appointment) -> str:
        return obj.space.title

    list_display = (
        "id",
        "space_name",
        "title",
        "created",
        "creator",
    )

    list_filter = (("created", DateRangeQuickSelectListFilterBuilder()),)
    search_fields = (
        "title",
        "space_name",
    )
