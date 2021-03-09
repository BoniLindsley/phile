#!/usr/bin/env python3

# Standard library.
import contextvars
import datetime
import functools
import typing

# External dependencies.
import PySide2.QtCore

wait_for_timeout: contextvars.ContextVar[datetime.timedelta] = (
    contextvars.ContextVar(
        'wait_for_timeout', default=datetime.timedelta(seconds=2)
    )
)
"""Default timeout value when processing PySide2 events."""


def process_deferred_delete_events() -> None:
    # Calling `processEvents` does not process `DeferredDelete` events.
    # Asking `sendPostedEvents` to process all events
    # (which is done by`processEvents`, I think)
    # also does not process it.
    # So this needs to be explicitly called.
    PySide2.QtCore.QCoreApplication.sendPostedEvents(
        None, PySide2.QtCore.QEvent.DeferredDelete
    )


def process_events() -> None:
    PySide2.QtCore.QCoreApplication.processEvents(
        PySide2.QtCore.QEventLoop.AllEvents,
        int(wait_for_timeout.get() / datetime.timedelta(milliseconds=1))
    )


class CallRequest(PySide2.QtCore.QEvent):

    event_type = PySide2.QtCore.QEvent.Type(  # type: ignore[call-arg]
        PySide2.QtCore.QEvent.registerEventType()
    )

    def __init__(
        self, callback: typing.Callable[[], typing.Any]
    ) -> None:
        """
        :param callback:
            Callable to eventually call in the Qt event loop
            whenever ``self`` is.
        :type callback: typing.Callable[[], typing.Any]
        """
        super().__init__(self.event_type)
        self.callback = callback


class Caller(PySide2.QtCore.QObject):

    def customEvent(
        self, event_to_handle: PySide2.QtCore.QEvent
    ) -> None:
        """Internal."""
        if event_to_handle.type() == CallRequest.event_type:
            event_to_handle.callback()
            self.deleteLater()
        else:
            super().customEvent(event_to_handle)


def call_soon_threadsafe(
    callback: typing.Callable[..., typing.Any],
    *args: typing.Any,
    thread: typing.Optional[PySide2.QtCore.QThread] = None,
) -> None:
    """Schedule ``callback`` to be called in the Qt event loop."""
    if args:
        callback = functools.partial(callback, *args)
    if thread is None:
        thread = PySide2.QtCore.QCoreApplication.instance().thread()
    event_to_post = CallRequest(callback=callback)
    caller = Caller()
    try:
        caller.moveToThread(thread)
        caller.setParent(thread)
        PySide2.QtCore.QCoreApplication.postEvent(caller, event_to_post)
    except:
        caller.deleteLater()
        raise
