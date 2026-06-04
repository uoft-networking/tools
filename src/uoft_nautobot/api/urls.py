from rest_framework import routers
from .views import ArubaBlocklistView

router = routers.DefaultRouter()
router.register(viewset=ArubaBlocklistView, prefix='aruba-blocklist', basename='aruba-blocklist')
urlpatterns = router.urls
