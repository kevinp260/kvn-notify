"""Template tags for Django template projects.

{% load kvn_notify %}
{% kvn_notify_scripts %}         loads the browser script (once, before </body>)
{% kvn_notify_button %}          a button that turns notifications on and off
{% kvn_notify_unread_count %}    the user's unread inbox count
"""

from django import template
from django.middleware.csrf import get_token
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html

from kvn_notify.conf import notify_settings

register = template.Library()


def _base_url() -> str:
    return reverse("kvn_notify:vapid-key").rsplit("vapid-key/", 1)[0].rstrip("/")


@register.simple_tag(takes_context=True)
def kvn_notify_scripts(context, service_worker: str = ""):
    """service_worker: leave empty when your app registers its own service worker
    (add importScripts for kvn_notify/sw.js to it); pass "default" to use the
    package's ready-made worker instead."""
    worker = reverse("kvn_notify:service-worker") if service_worker == "default" else service_worker
    # Handed to the script so session logins work even with CSRF_COOKIE_HTTPONLY = True.
    request = context.get("request")
    csrf_token = get_token(request) if request is not None else ""
    return format_html(
        '<script src="{}" data-base-url="{}" data-service-worker="{}" data-inbox="{}" '
        'data-csrf-token="{}" defer></script>',
        static("kvn_notify/kvn-notify.js"),
        _base_url(),
        worker,
        "true" if notify_settings.INBOX else "false",
        csrf_token,
    )


@register.simple_tag
def kvn_notify_button(
    label_off="Turn on notifications",
    label_on="Turn off notifications",
    css_class="",
):
    return format_html(
        '<button type="button" class="{}" data-kvn-notify-button data-label-off="{}" '
        'data-label-on="{}">{}</button>',
        css_class,
        label_off,
        label_on,
        label_off,
    )


@register.simple_tag(takes_context=True)
def kvn_notify_unread_count(context):
    request = context.get("request")
    user = getattr(request, "user", None)
    if not notify_settings.INBOX or user is None or not user.is_authenticated:
        return 0
    from kvn_notify.models import Notification

    return Notification.objects.filter(user=user, in_inbox=True, read_at__isnull=True).count()
