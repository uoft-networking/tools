from django.urls import path
from .views import ArubaBlocklistView

urlpatterns = [
    path('aruba-blocklist/', ArubaBlocklistView.as_view(), name='aruba-blocklist'),
]
