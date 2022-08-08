from django.urls import path
from .views import ArubaBlacklistView

urlpatterns = [
    path('aruba-blacklist/', ArubaBlacklistView.as_view(), name='aruba-blacklist'),
]