import pytest

from kvn_notify import NotificationType, register
from kvn_notify.exceptions import ImproperlyConfiguredType
from kvn_notify.types import get_type, unregister


def test_format_strings_and_callables():
    ntype = NotificationType(key="t.render", title="Hi {user.name}", body=lambda ctx: f"{ctx['n']} new")

    class U:
        name = "Ana"

    assert ntype.render("title", {"user": U()}) == "Hi Ana"
    assert ntype.render("body", {"n": 3}) == "3 new"
    assert ntype.render("url", {}) == ""


def test_missing_context_value_names_the_problem():
    ntype = NotificationType(key="t.missing", title="Hi {name}")
    with pytest.raises(ImproperlyConfiguredType, match="name"):
        ntype.render("title", {})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"key": "", "title": "x"},
        {"key": "t.x", "title": "x", "channels": []},
        {"key": "t.x", "title": "x", "channels": ["push", "push"]},
        {"key": "t.x", "title": "x", "channels": ["push", "email"], "fallback": "email"},
        {"key": "t.x", "title": "x", "urgency": "urgent"},
    ],
)
def test_invalid_definitions(kwargs):
    with pytest.raises(ImproperlyConfiguredType):
        NotificationType(**kwargs)


def test_registering_twice():
    first = NotificationType(key="t.twice", title="x")
    register(first)
    register(NotificationType(key="t.twice", title="x"))  # identical: fine (autoreload)
    with pytest.raises(ImproperlyConfiguredType):
        register(NotificationType(key="t.twice", title="different"))
    assert get_type("t.twice") == first
    unregister("t.twice")


def test_types_from_apps_are_discovered():
    assert get_type("leave.approved").channels == ("email", "push")
    assert get_type("kvn_notify.test").required is True
