import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from kvn_notify.models import Notification, PushSubscription

SUBSCRIPTION = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/example-device",
    "keys": {"p256dh": "BNcRdreALRFX", "auth": "tBHItJI5svbpez7KI4CCXg"},
}


class ApiTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("demo", "demo@example.com", "demo")
        token = self.client.post("/api/token/", {"username": "demo", "password": "demo"}).json()["access"]
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def post(self, url, data=None, **extra):
        return self.client.post(url, json.dumps(data or {}), content_type="application/json", **extra)

    # The example endpoint is not a real push service, so skip the DNS check.
    @override_settings(KVN_NOTIFY={**settings.KVN_NOTIFY, "VALIDATE_PUSH_ENDPOINTS": False})
    def test_jwt_login_subscribes_a_device(self):
        self.assertEqual(self.post("/api/notify/subscriptions/", SUBSCRIPTION).status_code, 401)
        self.assertEqual(self.post("/api/notify/subscriptions/", SUBSCRIPTION, **self.auth).status_code, 201)
        self.assertEqual(PushSubscription.objects.get().user.username, "demo")

    def test_user_without_devices_gets_the_email_fallback(self):
        self.assertEqual(self.post("/api/demo/send/", **self.auth).status_code, 202)
        self.assertTrue(Notification.objects.get().in_inbox)
        call_command("notify_worker", "--once", verbosity=0)
        self.assertEqual(len(mail.outbox), 1)

    def test_inbox_lists_the_notification(self):
        self.post("/api/demo/send/", **self.auth)
        inbox = self.client.get("/api/notify/inbox/", **self.auth).json()
        self.assertEqual(inbox["unread_count"], 1)
        self.assertEqual(inbox["results"][0]["title"].split(" added ")[0], "Ana")

    def test_startup_checks_pass(self):
        call_command("check", fail_level="WARNING")
