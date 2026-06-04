from django.urls import path
from .excel import DeviceInterfacesExcel


urlpatterns = [
    # ... previously defined urls
    path(
        "interfaces-excel/<uuid:pk>/",
        DeviceInterfacesExcel.as_view(),
        name="device_interfaces_excel",
    ),
]
