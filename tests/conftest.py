import contextlib
from dataclasses import dataclass, field

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("alice", "alice@example.com", "pw")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user("bob", "bob@example.com", "pw")


@pytest.fixture
def device(user):
    from kvn_notify.models import PushSubscription

    return PushSubscription.objects.create(
        user=user, endpoint="https://push.example.com/send/abc", p256dh="p256dh-key", auth="auth-secret"
    )


@pytest.fixture
def config():
    """Change some KVN_NOTIFY keys for one test: `with config(DISPATCH="worker"):`."""

    @contextlib.contextmanager
    def _config(**overrides):
        merged = {**settings.KVN_NOTIFY, **overrides}
        with override_settings(KVN_NOTIFY=merged):
            yield

    return _config


@dataclass
class FakePush:
    """Stands in for pywebpush.webpush and records each call."""

    calls: list = field(default_factory=list)
    fail_with: int | None = None

    def __call__(self, **kwargs):
        from pywebpush import WebPushException

        self.calls.append(kwargs)
        if self.fail_with is not None:
            response = type("Response", (), {"status_code": self.fail_with, "text": ""})()
            raise WebPushException(f"push failed with {self.fail_with}", response=response)


@pytest.fixture
def push(monkeypatch):
    fake = FakePush()
    monkeypatch.setattr("pywebpush.webpush", fake)
    return fake
