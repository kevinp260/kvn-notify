import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from kvn_notify import notify
from kvn_notify.models import Notification


@login_required
def home(request):
    return render(request, "demo/home.html")


# --8<-- [start:send]
@login_required
@require_POST
def send_demo(request):
    notify(
        request.user,
        "demo.order_shipped",
        {"order_number": f"#{random.randint(1000, 9999)}", "arrival": "tomorrow"},
    )
    messages.success(request, "Sent. It arrives within a few seconds.")
    return redirect("home")


# --8<-- [end:send]


@login_required
def inbox(request):
    notifications = Notification.objects.filter(user=request.user, in_inbox=True)[:50]
    return render(request, "demo/inbox.html", {"notifications": notifications})


def service_worker(request):
    # Served from the site root so it controls the whole site.
    response = render(request, "demo/sw.js", content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    return response
