from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from kvn_notify.models import Notification


class DemoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("demo", "demo@example.com", "demo")
        self.client.force_login(self.user)

    def test_home_has_the_button_and_script(self):
        page = self.client.get("/").content.decode()
        self.assertIn("data-kvn-notify-button", page)
        self.assertIn("/static/kvn_notify/kvn-notify.js", page)

    def test_service_worker_imports_the_push_handlers(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertIn(b'importScripts("/static/kvn_notify/sw.js")', response.content)

    def test_sending_reaches_email_and_inbox(self):
        self.client.post("/send/")
        notification = Notification.objects.get()
        self.assertTrue(notification.in_inbox)
        call_command("notify_worker", "--once", verbosity=0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(notification.title, self.client.get("/inbox/").content.decode())

    def test_startup_checks_pass(self):
        call_command("check", fail_level="WARNING")
