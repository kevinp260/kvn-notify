"""JSON endpoints used by the browser client (kvn-notify-web / subscribe.js)."""

from __future__ import annotations

import json
from functools import wraps
from pathlib import Path

from django.core.paginator import EmptyPage, Paginator
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from kvn_notify import inbox
from kvn_notify.api import get_preferences, set_preference
from kvn_notify.auth import AuthFailed, get_user
from kvn_notify.conf import notify_settings
from kvn_notify.devices import device_summary, list_devices, register_device, remove_device
from kvn_notify.devices import send_test as send_test_push
from kvn_notify.exceptions import KvnNotifyError


def _error(message: str, status: int, code: str | None = None) -> JsonResponse:
    body = {"error": message}
    if code:
        body["code"] = code
    return JsonResponse(body, status=status)


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("The request body is not valid JSON.") from None
    if not isinstance(data, dict):
        raise ValueError("The request body must be a JSON object.")
    return data


def endpoint(*methods: str, auth: bool = True, inbox: bool = False):
    """Common handling: allowed methods, CSRF via auth.py, JSON errors."""

    def decorator(view):
        @csrf_exempt  # CSRF is enforced in auth.get_user for cookie-based logins
        @require_http_methods(list(methods))
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if inbox and not notify_settings.INBOX:
                return _error("The inbox is not enabled. Set KVN_NOTIFY['INBOX'] = True.", 404)
            if auth:
                try:
                    request.notify_user = get_user(request)
                except AuthFailed as exc:
                    return _error(str(exc), exc.status, exc.code)
            try:
                return view(request, *args, **kwargs)
            except ValueError as exc:
                return _error(str(exc), 400)

        return wrapper

    return decorator


@endpoint("GET", auth=False)
def vapid_key(request):
    key = notify_settings.VAPID_PUBLIC_KEY
    if not key:
        return _error("Web Push is not configured on the server (VAPID_PUBLIC_KEY is empty).", 503)
    return JsonResponse({"public_key": key})


_SW_SOURCE = None


def service_worker(request):
    """A ready-made service worker for apps that do not have their own. Push works
    whatever the worker's scope, so serving it under /notify/ is fine."""
    global _SW_SOURCE
    if _SW_SOURCE is None:
        _SW_SOURCE = (Path(__file__).parent / "static" / "kvn_notify" / "sw.js").read_text(encoding="utf-8")
    response = HttpResponse(_SW_SOURCE, content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response


@endpoint("GET", "POST", "DELETE")
def subscriptions(request):
    if request.method == "GET":
        return JsonResponse({"results": [device_summary(d) for d in list_devices(request.notify_user)]})
    data = _json_body(request)
    if request.method == "DELETE":
        endpoint_url = data.get("endpoint")
        if not isinstance(endpoint_url, str) or not endpoint_url:
            raise ValueError("'endpoint' is required.")
        remove_device(request.notify_user, endpoint_url)
        return HttpResponse(status=204)

    given_name = data.get("device_name")
    device, created = register_device(
        request.notify_user,
        data,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        device_name=given_name if isinstance(given_name, str) else "",
    )
    return JsonResponse({"id": device.pk, "created": created}, status=201 if created else 200)


@endpoint("DELETE")
def subscription_detail(request, device_id):
    """Remove one of the user's devices by id, e.g. a lost phone from a device list."""
    from kvn_notify.models import PushSubscription

    deleted, _ = PushSubscription.objects.filter(pk=device_id, user=request.notify_user).delete()
    if not deleted:
        return _error("No such device.", 404)
    return HttpResponse(status=204)


@endpoint("POST")
def send_test(request):
    devices = send_test_push(request.notify_user)
    if not devices:
        return _error("This account has no devices subscribed to notifications.", 409)
    return JsonResponse({"devices": devices}, status=202)


@endpoint("GET", "POST")
def preferences(request):
    if request.method == "POST":
        data = _json_body(request)
        try:
            set_preference(
                request.notify_user,
                str(data.get("type", "")),
                str(data.get("channel", "")),
                bool(data.get("enabled")),
            )
        except KvnNotifyError as exc:
            raise ValueError(str(exc)) from None
    return JsonResponse({"results": get_preferences(request.notify_user)})


@endpoint("GET", inbox=True)
def inbox_list(request):
    queryset = inbox.inbox_items(request.notify_user, unread_only=request.GET.get("unread") in ("1", "true"))
    try:
        page_size = min(max(int(request.GET.get("page_size", 20)), 1), 100)
        page_number = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        raise ValueError("'page' and 'page_size' must be numbers.") from None
    paginator = Paginator(queryset, page_size)
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        page = None
    return JsonResponse(
        {
            "results": [inbox.serialize(n) for n in page] if page else [],
            "count": paginator.count,
            "page": page_number,
            "next_page": page.next_page_number() if page and page.has_next() else None,
            "unread_count": inbox.unread_count(request.notify_user),
        }
    )


@endpoint("GET", inbox=True)
def inbox_unread_count(request):
    return JsonResponse({"unread_count": inbox.unread_count(request.notify_user)})


@endpoint("POST", inbox=True)
def inbox_mark_read(request, notification_id):
    if not inbox.mark_read(request.notify_user, notification_id):
        return _error("Notification not found.", 404)
    return HttpResponse(status=204)


@endpoint("POST", inbox=True)
def inbox_mark_all_read(request):
    return JsonResponse({"marked": inbox.mark_all_read(request.notify_user)})
