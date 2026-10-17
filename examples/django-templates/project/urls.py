from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from demo import views

urlpatterns = [
    path("", views.home, name="home"),
    path("send/", views.send_demo, name="send-demo"),
    path("inbox/", views.inbox, name="inbox"),
    path("sw.js", views.service_worker, name="service-worker"),
    path("login/", auth_views.LoginView.as_view(template_name="demo/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("notify/", include("kvn_notify.urls")),
]
