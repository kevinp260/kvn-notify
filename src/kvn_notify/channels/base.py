from __future__ import annotations

from dataclasses import dataclass

from kvn_notify.exceptions import UnknownChannel


@dataclass(frozen=True)
class SendResult:
    """What a channel reports after one attempt."""

    status: str  # "sent", "retry" or "failed"
    error: str = ""

    @classmethod
    def sent(cls) -> SendResult:
        return cls("sent")

    @classmethod
    def retry(cls, error: str) -> SendResult:
        return cls("retry", error)

    @classmethod
    def failed(cls, error: str) -> SendResult:
        return cls("failed", error)


class Channel:
    """A way of reaching a person. Subclass it to add one (SMS, Slack, ...) and
    register it with kvn_notify.channels.register_channel()."""

    name: str = ""

    def create_deliveries(self, notification) -> list:
        """Create the Delivery rows for this notification. Return an empty list
        when this channel cannot reach the recipient (no devices, no address)."""
        raise NotImplementedError

    def send(self, delivery) -> SendResult:
        """Make one attempt. Must not raise: report errors through SendResult."""
        raise NotImplementedError


_channels: dict[str, Channel] = {}


def register_channel(channel: Channel) -> Channel:
    if not channel.name:
        raise ValueError("A channel needs a name.")
    _channels[channel.name] = channel
    return channel


def get_channel(name: str) -> Channel:
    try:
        return _channels[name]
    except KeyError:
        raise UnknownChannel(
            f"No channel named {name!r}. Built-in channels are 'push', 'email' and 'inbox'."
        ) from None


def channel_names() -> list[str]:
    return sorted(_channels)
