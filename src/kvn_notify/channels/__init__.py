from kvn_notify.channels.base import Channel, SendResult, channel_names, get_channel, register_channel

__all__ = ["Channel", "SendResult", "channel_names", "get_channel", "register_channel"]


def register_builtin_channels() -> None:
    from kvn_notify.channels.email import EmailChannel
    from kvn_notify.channels.inbox import InboxChannel
    from kvn_notify.channels.webpush import WebPushChannel

    for channel in (WebPushChannel(), EmailChannel(), InboxChannel()):
        register_channel(channel)
