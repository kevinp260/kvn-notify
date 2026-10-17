import pytest

from kvn_notify.devices import describe_user_agent

ANDROID_CHROME = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0.0.0 Mobile Safari/537.36"
)


@pytest.mark.parametrize(
    "agent, name",
    [
        (ANDROID_CHROME, "Chrome on Android"),
        (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/141.0.0.0 Safari/537.36",
            "Chrome on Linux",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0",
            "Firefox on Windows",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/18.6 Mobile/15E148 Safari/604.1",
            "Safari on iPhone",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
            "Edge on Windows",
        ),
        (
            "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) "
            "SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
            "Samsung Internet on Android",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/18.6 Safari/605.1.15",
            "Safari on macOS",
        ),
        ("SomethingUnknown/1.0", "Browser"),
        ("", "Browser"),
    ],
)
def test_describe_user_agent(agent, name):
    assert describe_user_agent(agent) == name


def test_existing_devices_are_named_by_the_migration(user):
    from importlib import import_module

    from django.apps import apps

    from kvn_notify.models import PushSubscription

    migration = import_module("kvn_notify.migrations.0002_pushsubscription_device_name")
    agents = {"a": ANDROID_CHROME, "b": "Android", "c": ""}
    for key, agent in agents.items():
        PushSubscription.objects.create(
            user=user, endpoint=f"https://push.example.com/{key}", p256dh="k", auth="s", user_agent=agent
        )
    PushSubscription.objects.update(device_name="")

    migration.name_existing_devices(apps, None)

    names = dict(PushSubscription.objects.values_list("endpoint", "device_name"))
    assert names == {
        "https://push.example.com/a": "Chrome on Android",
        "https://push.example.com/b": "Android",  # an old short label is kept as it was
        "https://push.example.com/c": "Browser",
    }
