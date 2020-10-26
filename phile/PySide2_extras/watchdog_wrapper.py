#!/usr/bin/env python3
"""
----------------------------------
Process watchdog events in PySide2
----------------------------------
"""

# Standard library.
import typing

# External dependencies.
from PySide2.QtCore import (
    QCoreApplication, QEvent, QObject, Signal, SignalInstance
)
import watchdog.events  # type: ignore[import]

# Internal package.
import phile.watchdog_extras


class SignalEmitter(QObject):
    """
    Forwards :class:`~watchdog.events.FileSystemEvent`
    to ``event_handler`` in Qt event loop
    if `self` is called with one.
    """

    _watchdog_dispatch = QEvent.Type(  # type: ignore[call-arg]
        QEvent.registerEventType()
    )
    """
    Internal.
    A Qt event posted to ``self`` when ``self`` is called.

    The event is expected to have a ``watchdog_event`` attribute
    containing the :class:`~watchdog.events.FileSystemEvent`
    that ``self`` was called with.
    """

    dispatched = typing.cast(
        SignalInstance, Signal(watchdog.events.FileSystemEvent)
    )
    """
    A Qt signal emitted after ``self`` is called.

    The :class:`~watchdog.events.FileSystemEvent` argument in the signal
    is expected to be the one ``self`` was called with.
    """

    def __init__(
        self, *args, event_handler: phile.watchdog_extras.EventHandler,
        **kwargs
    ) -> None:
        """
        :param event_handler:
            Callable for :class:`~watchdog.events.FileSystemEvent`-s
            to be forwarded to in Qt event loop.
            This is done by connecting to the :attr:`dispatched` signal,
            so automatic disconnection applies if ``event_handler``
            is a slot.
        :type event_handler:
            :data:`~phile.watchdog_extras.EventHandler` or :data:`None`
        """
        super().__init__(*args, **kwargs)
        self.dispatched.connect(event_handler)

    def __call__(self, watchdog_event: watchdog.events.FileSystemEvent):
        """
        Internal. Forward ``watchdog_event`` to self in Qt event loop.

        It is wrapped in a :attr:`_watchdog_dispatch` event
        which is then processed in :meth:`event`.

        This is thread-safe, as long as ``self`` is not destroyed,
        or being destroyed, before this method returns.
        That is, ensure ``self`` is removed as a watchdog handler
        before destroying it.
        """
        event_to_post = QEvent(self._watchdog_dispatch)
        event_to_post.watchdog_event = watchdog_event
        QCoreApplication.postEvent(self, event_to_post)

    def event(self, event_to_handle: QEvent) -> bool:
        """
        Internal.
        Emits a :attr:`dispatched` signal
        for each :attr:`_watchdog_dispatch` event
        that was :meth:`dispatch`-ed to ``self``.

        (Unless ``self`` is destroyed before the :meth:`dispatch`-ed
        event is processed here.)
        """
        if event_to_handle.type() != self._watchdog_dispatch:
            return super().event(event_to_handle)
        self.dispatched.emit(event_to_handle.watchdog_event)
        return True
