import io
import re
from pathlib import Path

import pytest
from django.core import mail
from django.core.checks import Error, Warning
from django.core.management import call_command
from PIL import Image

from kvn_notify import notify
from kvn_notify.checks import check_settings
from kvn_notify.icons import badge_problems, inspect_image
from kvn_notify.security import UnsafeEndpoint, check_push_endpoint

STATIC = Path(__file__).parent / "testapp" / "static" / "testapp"


def ids(problems):
    return sorted(p.id for p in problems)


def test_good_configuration_has_no_problems():
    assert check_settings() == []


def test_solid_small_badge_is_reported(config):
    with config(BADGE="testapp/solid-32.png"):
        problems = check_settings()
    assert ids(problems) == ["kvn_notify.W003", "kvn_notify.W005"]
    assert all(isinstance(p, Warning) for p in problems)
    assert "troubleshooting/#w003" in problems[0].hint


def test_strict_icons_turn_warnings_into_errors(config):
    with config(BADGE="testapp/solid-32.png", STRICT_ICONS=True):
        problems = check_settings()
    assert problems and all(isinstance(p, Error) for p in problems)


def test_missing_badge_icon_and_keys(config):
    with config(BADGE="", ICON="testapp/missing.png", VAPID_PRIVATE_KEY=""):
        problems = ids(check_settings())
    assert problems == ["kvn_notify.W001", "kvn_notify.W002", "kvn_notify.W006"]


def test_bad_dispatch_and_missing_site_url(config):
    with config(DISPATCH="cron", SITE_URL=""):
        assert ids(check_settings()) == ["kvn_notify.E001", "kvn_notify.W009"]


def test_app_icon_used_as_badge_is_reported(tmp_path):
    # A full-colour rounded-square app icon: transparent corners only.
    img = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    from PIL import ImageDraw

    ImageDraw.Draw(img).rounded_rectangle((0, 0, 191, 191), radius=40, fill=(220, 40, 40, 255))
    path = tmp_path / "app-icon.png"
    img.save(path)
    assert [code for code, _ in badge_problems(inspect_image(str(path)))] == ["W004"]


def test_good_badge_passes():
    assert badge_problems(inspect_image(str(STATIC / "badge-96.png"))) == []


def test_make_badge_turns_a_solid_logo_into_a_good_badge(tmp_path):
    logo = Image.new("RGB", (300, 200), (255, 255, 255))
    from PIL import ImageDraw

    ImageDraw.Draw(logo).ellipse((100, 50, 200, 150), fill=(10, 80, 200))
    source = tmp_path / "logo.png"
    logo.save(source)
    call_command("notify_make_badge", str(source), stdout=io.StringIO())

    badge_path = tmp_path / "logo-badge-96.png"
    with Image.open(badge_path) as badge:
        assert badge.size == (96, 96) and badge.mode == "RGBA"
        assert badge.getpixel((48, 48)) == (255, 255, 255, 255)
        assert badge.getpixel((2, 2))[3] == 0
    assert badge_problems(inspect_image(str(badge_path))) == []


def test_vapid_keys_command_prints_both_keys():
    out = io.StringIO()
    call_command("notify_vapid_keys", stdout=out, stderr=io.StringIO())
    text = out.getvalue()
    assert re.search(r"^VAPID_PUBLIC_KEY=[A-Za-z0-9_-]{87}$", text, re.M)
    assert re.search(r"^VAPID_PRIVATE_KEY=[A-Za-z0-9_-]{43}$", text, re.M)


@pytest.mark.django_db(transaction=True)
def test_worker_once_sends_what_is_due(user, config):
    with config(DISPATCH="worker"):
        notify(user, "leave.approved", {"leave_type": "x", "dates": "y", "leave_id": 1}, channels=["email"])
        assert mail.outbox == []
        out = io.StringIO()
        call_command("notify_worker", "--once", stdout=out)
    assert len(mail.outbox) == 1
    assert "sent=1" in out.getvalue()


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://push.example.com/x",
        "https://127.0.0.1/x",
        "https://10.0.0.5/x",
        "https://[::1]/x",
        "https:///x",
    ],
)
def test_unsafe_endpoints(endpoint):
    with pytest.raises(UnsafeEndpoint):
        check_push_endpoint(endpoint)


def test_public_ip_endpoint_is_allowed():
    check_push_endpoint("https://8.8.8.8/push")


def test_custom_functions_that_cannot_be_imported(config):
    with config(AUTH="myapp.auth.missing", PERMISSION="myapp.access.missing"):
        problems = check_settings()
    assert ids(problems) == ["kvn_notify.E005", "kvn_notify.E005"]
    assert "PERMISSION" in " ".join(p.msg for p in problems)


def test_importable_custom_functions_pass(config):
    with config(
        AUTH="tests.test_views.find_user_from_header", PERMISSION="tests.test_views.find_user_from_header"
    ):
        assert check_settings() == []


def test_make_badge_drops_a_faint_glow_around_the_logo(tmp_path):
    from PIL import ImageDraw, ImageFilter

    logo = Image.new("RGB", (200, 200), (255, 255, 255))
    glow = Image.new("RGB", (200, 200), (255, 255, 255))
    ImageDraw.Draw(glow).ellipse((20, 20, 180, 180), fill=(235, 235, 235))  # faint halo, difference 20
    logo.paste(glow.filter(ImageFilter.GaussianBlur(4)))
    ImageDraw.Draw(logo).ellipse((70, 70, 130, 130), fill=(20, 60, 200))
    source = tmp_path / "glow.png"
    logo.save(source)
    call_command("notify_make_badge", str(source), stdout=io.StringIO())

    with Image.open(tmp_path / "glow-badge-96.png") as badge:
        alpha = badge.getchannel("A")
        # The symbol fills the badge; the halo left no faint marks around it.
        assert alpha.getpixel((48, 48)) == 255
        assert sum(alpha.histogram()[1:255]) < 0.1 * 96 * 96
