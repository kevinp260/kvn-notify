"""Example-only helper: use VAPID keys from the environment, or create and keep a pair.

Real projects should generate keys once with `python manage.py notify_vapid_keys`
and store them as secrets. Changing keys stops every subscribed device.
"""

import os
from pathlib import Path


def load_or_create_vapid_keys(path: Path) -> tuple[str, str]:
    public, private = os.environ.get("VAPID_PUBLIC_KEY"), os.environ.get("VAPID_PRIVATE_KEY")
    if public and private:
        return public, private
    if not path.exists():
        from cryptography.hazmat.primitives import serialization
        from py_vapid import Vapid
        from py_vapid.utils import b64urlencode

        vapid = Vapid()
        vapid.generate_keys()
        private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
        public_raw = vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        path.write_text(
            f"VAPID_PUBLIC_KEY={b64urlencode(public_raw)}\nVAPID_PRIVATE_KEY={b64urlencode(private_raw)}\n"
        )
    values = dict(line.split("=", 1) for line in path.read_text().split())
    return values["VAPID_PUBLIC_KEY"], values["VAPID_PRIVATE_KEY"]
