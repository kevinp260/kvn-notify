from django.urls import path

from kvn_notify import views

app_name = "kvn_notify"

urlpatterns = [
    path("vapid-key/", views.vapid_key, name="vapid-key"),
    path("sw.js", views.service_worker, name="service-worker"),
    path("subscriptions/", views.subscriptions, name="subscriptions"),
    path("test/", views.send_test, name="test"),
    path("preferences/", views.preferences, name="preferences"),
    path("inbox/", views.inbox_list, name="inbox"),
    path("inbox/unread-count/", views.inbox_unread_count, name="inbox-unread-count"),
    path("inbox/read-all/", views.inbox_mark_all_read, name="inbox-read-all"),
    path("inbox/<uuid:notification_id>/read/", views.inbox_mark_read, name="inbox-read"),
]
