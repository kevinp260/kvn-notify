from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand
from py_vapid import Vapid
from py_vapid.utils import b64urlencode


class Command(BaseCommand):
    help = "Generate a VAPID key pair for Web Push and print it ready for your settings or .env file."

    def handle(self, *args, **options):
        vapid = Vapid()
        vapid.generate_keys()
        private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
        public_raw = vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.stdout.write(f"VAPID_PUBLIC_KEY={b64urlencode(public_raw)}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={b64urlencode(private_raw)}")
        self.stderr.write(
            "Keep the private key secret and back it up. Generate keys once per app: every device "
            "subscribed with the old keys stops receiving notifications if you change them."
        )
