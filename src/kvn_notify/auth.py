"""Finding the logged-in user for the package's endpoints.

KVN_NOTIFY["AUTH"]:
- "auto" (default): Django REST framework's authentication if DRF is installed
  (so SimpleJWT, TokenAuthentication, SessionAuthentication all work), else "session".
- "session": Django's session cookie.
- "drf": always use DRF's DEFAULT_AUTHENTICATION_CLASSES.
- "path.to.function": your function(request) -> user or None.

One CSRF rule applies in every mode: a request that changes something (POST,
DELETE, ...) and carries none of KVN_NOTIFY["TOKEN_HEADERS"] (default:
Authorization) must pass Django's CSRF check. Without a token header the login
can only have come from a cookie, which a browser attaches to forged requests
too. Requests with a token header skip it, as nothing attaches those
automatically. In "session" mode the check always runs. KVN_NOTIFY["ENFORCE_CSRF"] =
False turns the rule off for the other modes (warning W010); logins that check CSRF
themselves, such as DRF's SessionAuthentication, still do.

KVN_NOTIFY["PERMISSION"] (optional): a dotted path to a function(request, user) -> bool
run after the user is found, e.g. to require a verified second factor or staff status.
"""

from __future__ import annotations

import importlib.util

from django.middleware.csrf import CsrfViewMiddleware
from django.utils.module_loading import import_string

from kvn_notify.conf import notify_settings

CSRF_FAILED = "csrf_failed"


class AuthFailed(Exception):
    """``code`` is sent with the error so clients can tell cases apart; "csrf_failed"
    means only the CSRF token was refused, and a fresh one will do."""

    def __init__(self, message: str, status: int = 401, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


def _mode() -> str:
    mode = notify_settings.AUTH or "auto"
    if mode == "auto":
        return "drf" if importlib.util.find_spec("rest_framework") else "session"
    return mode


SAFE_METHODS = ("GET", "HEAD", "OPTIONS", "TRACE")


def get_user(request):
    """Return the authenticated user, or raise AuthFailed."""
    mode = _mode()
    if mode == "session":
        user = _session_user(request)
    elif mode == "drf":
        user = _drf_user(request)
    else:
        user = import_string(mode)(request)
    if user is None or not getattr(user, "is_authenticated", False):
        raise AuthFailed("Authentication credentials were not provided or are invalid.", 401)
    # A "session" login always came from the cookie, whatever headers are present.
    if mode == "session" or (notify_settings.ENFORCE_CSRF and not has_token_header(request)):
        _enforce_csrf(request)
    permission = notify_settings.PERMISSION
    if permission:
        check = import_string(permission) if isinstance(permission, str) else permission
        if not check(request, user):
            raise AuthFailed("You do not have permission to manage notifications.", 403)
    return user


def has_token_header(request) -> bool:
    """True when the request carries a login that a browser never attaches by itself."""
    return any(request.headers.get(name) for name in notify_settings.TOKEN_HEADERS)


def _session_user(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    return user


def _enforce_csrf(request) -> None:
    if request.method in SAFE_METHODS or getattr(request, "_kvn_notify_csrf_checked", False):
        return
    check = CsrfViewMiddleware(lambda req: None)
    check.process_request(request)
    rejected = check.process_view(request, None, (), {})
    if rejected is not None:
        raise AuthFailed(
            "CSRF check failed. Send the X-CSRFToken header with the csrftoken cookie value.",
            403,
            code=CSRF_FAILED,
        )
    request._kvn_notify_csrf_checked = True


def _drf_user(request):
    from rest_framework import exceptions
    from rest_framework.request import Request
    from rest_framework.settings import api_settings

    # SessionAuthentication's CSRF check reads request.POST, which makes DRF parse the
    # body. Read the body first so Django keeps a copy for the view, and give DRF the
    # project's parsers so a JSON body parses instead of failing.
    request.body  # noqa: B018
    drf_request = Request(
        request,
        parsers=[cls() for cls in api_settings.DEFAULT_PARSER_CLASSES],
        authenticators=[cls() for cls in api_settings.DEFAULT_AUTHENTICATION_CLASSES],
    )
    try:
        user = drf_request.user  # runs each authenticator; SessionAuthentication enforces CSRF
    except exceptions.AuthenticationFailed as exc:
        raise AuthFailed(str(exc.detail), 401) from exc
    except exceptions.PermissionDenied as exc:
        # DRF's SessionAuthentication and dj-rest-auth's JWT cookie both refuse a bad
        # token with "CSRF Failed: <reason>".
        code = CSRF_FAILED if str(exc.detail).startswith("CSRF Failed") else None
        raise AuthFailed(str(exc.detail), 403, code=code) from exc
    except exceptions.APIException as exc:
        raise AuthFailed(str(exc.detail), exc.status_code) from exc
    return user
