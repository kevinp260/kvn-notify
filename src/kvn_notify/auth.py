"""Finding the logged-in user for the package's endpoints.

KVN_NOTIFY["AUTH"]:
- "auto" (default): Django REST framework's authentication if DRF is installed
  (so SimpleJWT, TokenAuthentication, SessionAuthentication all work), else "session".
- "session": Django's session cookie, with CSRF checks on unsafe methods.
- "drf": always use DRF's DEFAULT_AUTHENTICATION_CLASSES.
- "path.to.function": your function(request) -> user or None. CSRF is then your
  function's responsibility.

KVN_NOTIFY["PERMISSION"] (optional): a dotted path to a function(request, user) -> bool
run after the user is found, e.g. to require a verified second factor or staff status.
"""

from __future__ import annotations

import importlib.util

from django.middleware.csrf import CsrfViewMiddleware
from django.utils.module_loading import import_string

from kvn_notify.conf import notify_settings


class AuthFailed(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


def _mode() -> str:
    mode = notify_settings.AUTH or "auto"
    if mode == "auto":
        return "drf" if importlib.util.find_spec("rest_framework") else "session"
    return mode


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
    permission = notify_settings.PERMISSION
    if permission:
        check = import_string(permission) if isinstance(permission, str) else permission
        if not check(request, user):
            raise AuthFailed("You do not have permission to manage notifications.", 403)
    return user


def _session_user(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    _enforce_csrf(request)
    return user


def _enforce_csrf(request) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
        return
    check = CsrfViewMiddleware(lambda req: None)
    check.process_request(request)
    rejected = check.process_view(request, None, (), {})
    if rejected is not None:
        raise AuthFailed(
            "CSRF check failed. Send the X-CSRFToken header with the csrftoken cookie value.", 403
        )


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
        raise AuthFailed(str(exc.detail), 403) from exc
    except exceptions.APIException as exc:
        raise AuthFailed(str(exc.detail), exc.status_code) from exc
    return user
