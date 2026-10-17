from django.urls import include, path

urlpatterns = [
    path("notify/", include("kvn_notify.urls")),
]
