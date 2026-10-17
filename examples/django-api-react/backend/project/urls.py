from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api import views

urlpatterns = [
    path("api/token/", TokenObtainPairView.as_view()),
    path("api/token/refresh/", TokenRefreshView.as_view()),
    path("api/demo/send/", views.SendDemo.as_view()),
    # --8<-- [start:urls]
    path("api/notify/", include("kvn_notify.urls")),
    # --8<-- [end:urls]
    path("admin/", admin.site.urls),
]
