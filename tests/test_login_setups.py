"""Every supported way an app can log users in, against one endpoint.

Each case subscribes a device (POST /notify/subscriptions/) with a client that
enforces CSRF like a real browser. The rule under test is the same in every mode:
a login from a cookie needs the CSRF token; a login from a token header does not.
"""

import json

import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db(transaction=True)

URL = "/notify/subscriptions/"
SUBSCRIPTION = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/setup-test",
    "keys": {"p256dh": "BNcRdreALRFX", "auth": "tBHItJI5svbpez7KI4CCXg"},
}
CSRF_TOKEN = "a" * 32


def post(client, **headers):
    return client.post(URL, json.dumps(SUBSCRIPTION), content_type="application/json", **headers)


def browser():
    """A client that, like a browser, gets no free pass on CSRF."""
    client = Client(enforce_csrf_checks=True)
    client.cookies["csrftoken"] = CSRF_TOKEN
    return client


@pytest.fixture
def drf(config):
    """Switch kvn-notify to DRF mode with the given authentication classes."""
    from rest_framework.settings import api_settings

    def use(*classes):
        override = override_settings(REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": list(classes)})
        override.enable()
        api_settings.reload()
        cfg = config(AUTH="drf")
        cfg.__enter__()
        stack.append((override, cfg))

    stack = []
    yield use
    for override, cfg in reversed(stack):
        cfg.__exit__(None, None, None)
        override.disable()
    api_settings.reload()


# 1. Django session cookie (Django templates, same-site frontends) ------------


def test_django_session_cookie(user):
    client = browser()
    client.force_login(user)
    assert post(client).status_code == 403
    assert post(client, HTTP_X_CSRFTOKEN=CSRF_TOKEN).status_code == 201


def test_session_mode_checks_csrf_even_with_a_token_header(user):
    # In "session" mode the login can only have come from the cookie.
    client = browser()
    client.force_login(user)
    assert post(client, HTTP_AUTHORIZATION="Bearer anything").status_code == 403


# 2. DRF SessionAuthentication (e.g. React + allauth headless browser mode) ------


def test_drf_session_authentication(user, drf):
    drf("rest_framework.authentication.SessionAuthentication")
    client = browser()
    client.force_login(user)
    assert post(client).status_code == 403
    assert post(client, HTTP_X_CSRFTOKEN=CSRF_TOKEN).status_code == 201


# 3. JWT in a header (Simple JWT): browser-held tokens, mobile apps, proxies ---


def test_simple_jwt_header(user, drf):
    from rest_framework_simplejwt.tokens import AccessToken

    drf("rest_framework_simplejwt.authentication.JWTAuthentication")
    token = str(AccessToken.for_user(user))
    # No CSRF token and no cookies: nothing here is sent automatically by a browser.
    assert post(Client(enforce_csrf_checks=True), HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 201
    assert post(Client(), HTTP_AUTHORIZATION="Bearer not-a-token").status_code == 401
    assert post(Client()).status_code == 401


def test_proxy_forwarding_a_header_token(user, drf):
    # A backend-for-frontend (e.g. a Next.js route) turns its own cookie into a
    # header; Django only sees the header, plus whatever cookies the proxy forwards.
    from rest_framework_simplejwt.tokens import AccessToken

    drf("rest_framework_simplejwt.authentication.JWTAuthentication")
    client = Client(enforce_csrf_checks=True)
    client.cookies["unrelated"] = "x"
    token = str(AccessToken.for_user(user))
    assert post(client, HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 201


# 4. DRF TokenAuthentication ---------------------------------------------------


def test_drf_token_authentication(user, drf):
    from rest_framework.authtoken.models import Token

    drf("rest_framework.authentication.TokenAuthentication")
    token = Token.objects.create(user=user)
    assert post(Client(enforce_csrf_checks=True), HTTP_AUTHORIZATION=f"Token {token.key}").status_code == 201


# 5. JWT in an HttpOnly cookie (dj-rest-auth) ----------------------------------


def test_jwt_cookie_needs_csrf_even_when_the_login_library_skips_it(user, drf):
    """dj-rest-auth checks CSRF only if JWT_AUTH_COOKIE_USE_CSRF is on (off by default).
    kvn-notify's rule covers it: the token came in a cookie, so CSRF is required."""
    from rest_framework_simplejwt.tokens import AccessToken

    drf("dj_rest_auth.jwt_auth.JWTCookieAuthentication")
    client = browser()
    client.cookies["app-auth"] = str(AccessToken.for_user(user))
    assert post(client).status_code == 403
    assert post(client, HTTP_X_CSRFTOKEN=CSRF_TOKEN).status_code == 201


# 6. Custom login functions ----------------------------------------------------


def user_from_cookie(request):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(username=request.COOKIES.get("my-login", "")).first()


def user_from_api_key(request):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(username=request.headers.get("X-Api-Key", "")).first()


def user_from_allauth_app_token(request):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(username=request.headers.get("X-Session-Token", "")).first()


def test_custom_cookie_login_gets_csrf_protection_for_free(user, config):
    client = browser()
    client.cookies["my-login"] = "alice"
    with config(AUTH="tests.test_login_setups.user_from_cookie"):
        assert post(client).status_code == 403
        assert post(client, HTTP_X_CSRFTOKEN=CSRF_TOKEN).status_code == 201


def test_custom_header_login_lists_its_header(user, config):
    client = Client(enforce_csrf_checks=True)
    with config(AUTH="tests.test_login_setups.user_from_api_key"):
        # Not a known token header yet, so it is treated like a cookie login.
        assert post(client, HTTP_X_API_KEY="alice").status_code == 403
    with config(AUTH="tests.test_login_setups.user_from_api_key", TOKEN_HEADERS=["X-Api-Key"]):
        assert post(client, HTTP_X_API_KEY="alice").status_code == 201


def test_allauth_app_token_header_is_known_by_default(user, config):
    client = Client(enforce_csrf_checks=True)
    with config(AUTH="tests.test_login_setups.user_from_allauth_app_token"):
        assert post(client, HTTP_X_SESSION_TOKEN="alice").status_code == 201


# Opting out --------------------------------------------------------------------


def test_the_rule_can_be_turned_off_with_a_warning(user, config):
    from kvn_notify.checks import check_settings

    client = browser()
    client.cookies["my-login"] = "alice"
    with config(AUTH="tests.test_login_setups.user_from_cookie", ENFORCE_CSRF=False):
        assert post(client).status_code == 201
        assert "kvn_notify.W010" in [p.id for p in check_settings()]


def test_readable_session_cookie_is_reported_in_production(settings):
    from kvn_notify.checks import check_settings

    settings.SESSION_COOKIE_HTTPONLY = False
    assert "kvn_notify.W011" in [p.id for p in check_settings()]
    settings.DEBUG = True
    assert "kvn_notify.W011" not in [p.id for p in check_settings()]
