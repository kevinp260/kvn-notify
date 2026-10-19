import json
import re

import pytest
from django.test import Client, override_settings

from kvn_notify import notify
from kvn_notify.models import Notification, PushSubscription

pytestmark = pytest.mark.django_db(transaction=True)

SUBSCRIPTION = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/device-1",
    "expirationTime": None,
    "keys": {"p256dh": "BNcRdreALRFX", "auth": "tBHItJI5svbpez7KI4CCXg"},
}


def post(client, url, data, **extra):
    return client.post(url, json.dumps(data), content_type="application/json", **extra)


@pytest.fixture
def logged_in(user):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.get("/notify/vapid-key/")  # any request; then set a CSRF cookie explicitly
    client.cookies["csrftoken"] = "a" * 32
    return client


def csrf(client):
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def test_vapid_key_is_public(client, config):
    assert client.get("/notify/vapid-key/").json() == {"public_key": "BPublicKeyForTests"}
    with config(VAPID_PUBLIC_KEY=""):
        assert client.get("/notify/vapid-key/").status_code == 503


def test_subscribing_needs_a_login(client):
    assert post(client, "/notify/subscriptions/", SUBSCRIPTION).status_code == 401


def test_session_login_needs_the_csrf_token(logged_in):
    response = post(logged_in, "/notify/subscriptions/", SUBSCRIPTION)
    assert response.status_code == 403
    assert "CSRF" in response.json()["error"]


def test_subscribe_update_and_unsubscribe(logged_in, user):
    first = post(logged_in, "/notify/subscriptions/", SUBSCRIPTION, **csrf(logged_in))
    assert first.status_code == 201 and first.json()["created"] is True
    again = post(logged_in, "/notify/subscriptions/", SUBSCRIPTION, **csrf(logged_in))
    assert again.status_code == 200
    assert PushSubscription.objects.get().user == user

    gone = logged_in.delete(
        "/notify/subscriptions/",
        json.dumps({"endpoint": SUBSCRIPTION["endpoint"]}),
        content_type="application/json",
        **csrf(logged_in),
    )
    assert gone.status_code == 204
    assert not PushSubscription.objects.exists()


def test_list_and_remove_devices(logged_in, user, other_user):
    import hashlib

    post(logged_in, "/notify/subscriptions/", SUBSCRIPTION, **csrf(logged_in),
         HTTP_USER_AGENT="Mozilla/5.0 (Linux; Android 14) Chrome/141.0 Mobile Safari/537.36")
    theirs = PushSubscription.objects.create(
        user=other_user, endpoint="https://push.example.com/theirs", p256dh="k", auth="a"
    )

    listed = logged_in.get("/notify/subscriptions/").json()["results"]
    assert len(listed) == 1
    [mine] = listed
    assert mine["name"] == "Chrome on Android" and mine["active"] is True
    # A browser recognises its own row without the server handing out addresses.
    assert mine["endpoint_hash"] == hashlib.sha256(SUBSCRIPTION["endpoint"].encode()).hexdigest()
    assert "endpoint" not in mine and "p256dh" not in mine and "auth" not in mine

    # Someone else's device: not found, and not removed.
    assert logged_in.delete(f"/notify/subscriptions/{theirs.pk}/", **csrf(logged_in)).status_code == 404
    assert PushSubscription.objects.filter(pk=theirs.pk).exists()
    # Removing changes data, so the CSRF rule applies.
    assert logged_in.delete(f"/notify/subscriptions/{mine['id']}/").status_code == 403

    assert logged_in.delete(f"/notify/subscriptions/{mine['id']}/", **csrf(logged_in)).status_code == 204
    assert not PushSubscription.objects.filter(user=user).exists()


def test_a_device_moves_to_whoever_logs_in(logged_in, user, other_user):
    post(logged_in, "/notify/subscriptions/", SUBSCRIPTION, **csrf(logged_in))
    bob = Client(enforce_csrf_checks=True)
    bob.force_login(other_user)
    bob.cookies["csrftoken"] = "b" * 32
    post(bob, "/notify/subscriptions/", SUBSCRIPTION, **csrf(bob))
    assert PushSubscription.objects.get().user == other_user


def test_bad_subscription_bodies_are_rejected(logged_in):
    assert post(logged_in, "/notify/subscriptions/", {}, **csrf(logged_in)).status_code == 400
    missing_keys = {"endpoint": SUBSCRIPTION["endpoint"]}
    assert post(logged_in, "/notify/subscriptions/", missing_keys, **csrf(logged_in)).status_code == 400
    http = {**SUBSCRIPTION, "endpoint": "http://push.example.com/x"}
    response = post(logged_in, "/notify/subscriptions/", http, **csrf(logged_in))
    assert response.status_code == 400 and "https" in response.json()["error"]
    not_json = logged_in.post(
        "/notify/subscriptions/", "nope", content_type="application/json", **csrf(logged_in)
    )
    assert not_json.status_code == 400


def test_private_endpoints_are_refused(logged_in, config):
    internal = {**SUBSCRIPTION, "endpoint": "https://127.0.0.1/steal"}
    with config(VALIDATE_PUSH_ENDPOINTS=True):
        response = post(logged_in, "/notify/subscriptions/", internal, **csrf(logged_in))
    assert response.status_code == 400


def test_test_push(logged_in, device, push):
    response = post(logged_in, "/notify/test/", {}, **csrf(logged_in))
    assert response.status_code == 202 and response.json() == {"devices": 1}
    assert json.loads(push.calls[0]["data"])["tag"] == "kvn-notify-test"


def test_test_push_without_devices(logged_in):
    assert post(logged_in, "/notify/test/", {}, **csrf(logged_in)).status_code == 409


def test_preferences_endpoint(logged_in):
    rows = logged_in.get("/notify/preferences/").json()["results"]
    assert any(row["type"] == "leave.approved" for row in rows)
    response = post(
        logged_in,
        "/notify/preferences/",
        {"type": "leave.approved", "channel": "email", "enabled": False},
        **csrf(logged_in),
    )
    row = next(r for r in response.json()["results"] if r["type"] == "leave.approved")
    assert row["channels"]["email"] is False
    bad = post(logged_in, "/notify/preferences/", {"type": "nope", "channel": "email"}, **csrf(logged_in))
    assert bad.status_code == 400


def test_inbox_endpoints(logged_in, user, other_user, push):
    for amount in ("1", "2", "3"):
        notify(user, "group.expense", {"who": "Ana", "amount": amount}, data={"group": 1})
    notify(other_user, "group.expense", {"who": "Ana", "amount": "9"})
    notify(user, "leave.approved", {"leave_type": "x", "dates": "y", "leave_id": 1})  # not an inbox type

    page = logged_in.get("/notify/inbox/?page_size=2").json()
    assert page["count"] == 3 and page["unread_count"] == 3 and page["next_page"] == 2
    assert page["results"][0]["title"] == "Ana added 3"
    assert page["results"][0]["data"] == {"group": 1}

    first_id = page["results"][0]["id"]
    assert post(logged_in, f"/notify/inbox/{first_id}/read/", {}, **csrf(logged_in)).status_code == 204
    assert logged_in.get("/notify/inbox/unread-count/").json() == {"unread_count": 2}
    assert len(logged_in.get("/notify/inbox/?unread=1").json()["results"]) == 2

    others = Notification.objects.get(user=other_user)
    assert post(logged_in, f"/notify/inbox/{others.pk}/read/", {}, **csrf(logged_in)).status_code == 404

    assert post(logged_in, "/notify/inbox/read-all/", {}, **csrf(logged_in)).json() == {"marked": 2}


def test_inbox_endpoints_are_off_when_inbox_is_disabled(logged_in, config):
    with config(INBOX=False):
        assert logged_in.get("/notify/inbox/").status_code == 404


def test_wrong_method(logged_in):
    assert logged_in.get("/notify/test/").status_code == 405
    assert logged_in.get("/notify/subscriptions/1/").status_code == 405


def test_service_worker_is_served(client):
    response = client.get("/notify/sw.js")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/javascript")
    assert b"registerPushHandlers" in response.content


class HeaderAuthentication:
    """A stand-in for SimpleJWT: reads the user from an Authorization header."""

    def authenticate(self, request):
        from django.contrib.auth import get_user_model
        from rest_framework.exceptions import AuthenticationFailed

        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header:
            return None
        if not header.startswith("Bearer "):
            raise AuthenticationFailed("Bad token.")
        user = get_user_model().objects.filter(username=header.removeprefix("Bearer ")).first()
        if user is None:
            raise AuthenticationFailed("Unknown token.")
        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"


DRF = {"DEFAULT_AUTHENTICATION_CLASSES": ["tests.test_views.HeaderAuthentication"]}


def test_drf_token_login_needs_no_csrf(user, config):
    client = Client(enforce_csrf_checks=True)
    with override_settings(REST_FRAMEWORK=DRF), config(AUTH="drf"):
        from rest_framework.settings import api_settings

        api_settings.reload()
        try:
            ok = post(client, "/notify/subscriptions/", SUBSCRIPTION, HTTP_AUTHORIZATION="Bearer alice")
            bad = post(client, "/notify/subscriptions/", SUBSCRIPTION, HTTP_AUTHORIZATION="Bearer nobody")
            none = post(client, "/notify/subscriptions/", SUBSCRIPTION)
        finally:
            api_settings.reload()
    assert ok.status_code == 201
    assert bad.status_code == 401
    assert none.status_code == 401


def find_user_from_header(request):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(username=request.headers.get("X-User", "")).first()


def test_custom_auth_function(user, config):
    client = Client()
    with config(AUTH="tests.test_views.find_user_from_header"):
        assert post(client, "/notify/subscriptions/", SUBSCRIPTION, HTTP_X_USER="alice").status_code == 201
        assert post(client, "/notify/subscriptions/", SUBSCRIPTION).status_code == 401


def test_template_tags_render(rf, user, push):
    from django.template import Context, Template

    notify(user, "group.expense", {"who": "Ana", "amount": "1"})
    request = rf.get("/")
    request.user = user
    html = Template(
        "{% load kvn_notify %}{% kvn_notify_scripts %}|{% kvn_notify_button %}|{% kvn_notify_unread_count %}"
    ).render(Context({"request": request}))
    scripts, button, count = html.split("|")
    assert 'src="/static/kvn_notify/kvn-notify.js"' in scripts
    assert 'data-base-url="/notify"' in scripts and 'data-inbox="true"' in scripts
    # The token travels in the page, so sessions work with CSRF_COOKIE_HTTPONLY = True.
    assert re.search(r'data-csrf-token="[A-Za-z0-9]{32,}"', scripts)
    assert "data-kvn-notify-button" in button and "Turn on notifications" in button
    assert count == "1"
    default_worker = Template('{% load kvn_notify %}{% kvn_notify_scripts "default" %}').render(Context({}))
    assert 'data-service-worker="/notify/sw.js"' in default_worker


SESSION_DRF = {"DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"]}


@pytest.mark.parametrize("with_token", [True, False])
def test_drf_session_login_with_a_json_body(user, config, with_token):
    """DRF's SessionAuthentication reads request.POST for its CSRF check; a JSON body
    must still parse, reach the view, and a missing token must give 403, not 500."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.cookies["csrftoken"] = "c" * 32
    headers = {"HTTP_X_CSRFTOKEN": "c" * 32} if with_token else {}
    with override_settings(REST_FRAMEWORK=SESSION_DRF), config(AUTH="drf"):
        from rest_framework.settings import api_settings

        api_settings.reload()
        try:
            response = post(
                client,
                "/notify/preferences/",
                {"type": "leave.approved", "channel": "email", "enabled": False},
                **headers,
            )
        finally:
            api_settings.reload()
    if with_token:
        assert response.status_code == 200
        row = next(r for r in response.json()["results"] if r["type"] == "leave.approved")
        assert row["channels"]["email"] is False
    else:
        assert response.status_code == 403


def test_devices_get_a_readable_name(logged_in):
    from tests.test_devices import ANDROID_CHROME

    post(logged_in, "/notify/subscriptions/", SUBSCRIPTION, HTTP_USER_AGENT=ANDROID_CHROME, **csrf(logged_in))
    assert PushSubscription.objects.get().device_name == "Chrome on Android"

    named = {**SUBSCRIPTION, "device_name": "  Kevin's   phone "}
    post(logged_in, "/notify/subscriptions/", named, HTTP_USER_AGENT=ANDROID_CHROME, **csrf(logged_in))
    device = PushSubscription.objects.get()
    assert device.device_name == "Kevin's phone"
    assert device.label == "Kevin's phone"
