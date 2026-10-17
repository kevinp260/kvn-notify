"""JSON endpoints used by the browser client (kvn-notify-web / subscribe.js)."""

from __future__ import annotations

import json
from functools import wraps
from pathlib import Path

from django.core.paginator import EmptyPage, Paginator
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from kvn_notify.api import get_preferences, notify, set_preference
from kvn_notify.auth import AuthFailed, get_user
from kvn_notify.conf import notify_settings
from kvn_notify.devices import describe_user_agent
from kvn_notify.exceptions import KvnNotifyError
from kvn_notify.models import Notification, PushSubscription, endpoint_hash
from kvn_notify.security import UnsafeEndpoint, check_push_endpoint


def _error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


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
                    return _error(str(exc), exc.status)
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


@endpoint("POST", "DELETE")
def subscriptions(request):
    data = _json_body(request)
    raw_endpoint = data.get("endpoint")
    if not isinstance(raw_endpoint, str) or not raw_endpoint:
        raise ValueError("'endpoint' is required.")
    if len(raw_endpoint) > 2048:
        raise ValueError("'endpoint' is too long.")

    if request.method == "DELETE":
        PushSubscription.objects.filter(
            endpoint_hash=endpoint_hash(raw_endpoint), user=request.notify_user
        ).delete()
        return HttpResponse(status=204)

    keys = data.get("keys") or {}
    p256dh, auth_secret = keys.get("p256dh"), keys.get("auth")
    if not (isinstance(p256dh, str) and isinstance(auth_secret, str) and p256dh and auth_secret):
        raise ValueError("'keys.p256dh' and 'keys.auth' are required.")
    if len(p256dh) > 255 or len(auth_secret) > 255:
        raise ValueError("Subscription keys are too long.")
    try:
        check_push_endpoint(raw_endpoint, resolve=notify_settings.VALIDATE_PUSH_ENDPOINTS)
    except UnsafeEndpoint as exc:
        raise ValueError(f"Refused push endpoint: {exc}") from None

    user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
    given_name = data.get("device_name")
    if not isinstance(given_name, str):
        given_name = ""
    subscription = PushSubscription.objects.filter(endpoint_hash=endpoint_hash(raw_endpoint)).first()
    created = subscription is None
    if created:
        subscription = PushSubscription(endpoint=raw_endpoint)
    # A device belongs to whoever is logged in on it now, so one phone never
    # receives two people's notifications.
    subscription.user = request.notify_user
    subscription.p256dh = p256dh
    subscription.auth = auth_secret
    subscription.user_agent = user_agent
    # A name the page sends wins; otherwise one is made from the browser's user agent.
    subscription.device_name = " ".join(given_name.split())[:120] or describe_user_agent(user_agent)
    subscription.active = True
    subscription.disabled_reason = ""
    subscription.disabled_at = None
    subscription.save()
    return JsonResponse({"id": subscription.pk, "created": created}, status=201 if created else 200)


@endpoint("POST")
def send_test(request):
    devices = PushSubscription.objects.filter(user=request.notify_user, active=True).count()
    if not devices:
        return _error("This account has no devices subscribed to notifications.", 409)
    notify(request.notify_user, "kvn_notify.test")
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


def _serialize(notification: Notification) -> dict:
    return {
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title,
        "body": notification.body,
        "url": notification.url,
        "data": notification.data,
        "read": notification.read_at is not None,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat(),
    }


def _inbox_queryset(user):
    return Notification.objects.filter(user=user, in_inbox=True)


@endpoint("GET", inbox=True)
def inbox_list(request):
    queryset = _inbox_queryset(request.notify_user)
    if request.GET.get("unread") in ("1", "true"):
        queryset = queryset.filter(read_at__isnull=True)
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
            "results": [_serialize(n) for n in page] if page else [],
            "count": paginator.count,
            "page": page_number,
            "next_page": page.next_page_number() if page and page.has_next() else None,
            "unread_count": _inbox_queryset(request.notify_user).filter(read_at__isnull=True).count(),
        }
    )


@endpoint("GET", inbox=True)
def inbox_unread_count(request):
    count = _inbox_queryset(request.notify_user).filter(read_at__isnull=True).count()
    return JsonResponse({"unread_count": count})


@endpoint("POST", inbox=True)
def inbox_mark_read(request, notification_id):
    updated = (
        _inbox_queryset(request.notify_user)
        .filter(pk=notification_id, read_at__isnull=True)
        .update(read_at=timezone.now())
    )
    if not updated and not _inbox_queryset(request.notify_user).filter(pk=notification_id).exists():
        return _error("Notification not found.", 404)
    return HttpResponse(status=204)


@endpoint("POST", inbox=True)
def inbox_mark_all_read(request):
    count = _inbox_queryset(request.notify_user).filter(read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({"marked": count})
