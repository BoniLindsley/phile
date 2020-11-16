#!/usr/bin/env python3
"""
-------------------------------
Interactions with Qt event loop
-------------------------------
"""

# Standard library.
import collections.abc

# External dependencies.
from PySide2.QtCore import QCoreApplication, QEvent, QObject


class CallSoon(QObject):
    """
    Schedule ``call_target`` to be called in the Qt event loop.

    The scheduling occurs whenever ``self`` is called,
    using the same arguments as the ``self`` call.
    """

    _call_request = QEvent.Type(  # type: ignore[call-arg]
        QEvent.registerEventType()
    )
    """
    Internal.
    A Qt event posted to ``self`` when ``self`` is called.

    The event is expected to have the ``args`` and ``kwargs`` attributes
    that ``self`` was called with.
    """

    def __init__(
        self, *args, call_target: collections.abc.Callable, **kwargs
    ) -> None:
        """
        :param collections.abc.Callable call_target:
            Callable to eventually call in the Qt event loop
            whenever ``self`` is.
        """
        super().__init__(*args, **kwargs)
        self._call_target = call_target

    def __call__(self, *args, **kwargs) -> None:
        """
        Internal. Post arguments to self in Qt event loop.

        This is thread-safe,
        as long as ``self`` is not destroyed, or being destroyed,
        while this method is called and before this method returns.
        When using this with the :std:doc:`watchdog:index` module,
        one way to guarantee this
        is to ensure ``self`` is removed from the watchdog dispatch chain
        before destroying it.

        Internal.
        Arguments are packed
        in attributes of a :attr:`_call_request` event
        which will then be posted and be processed in :meth:`event`.
        """
        event_to_post = QEvent(self._call_request)
        event_to_post.args = args
        event_to_post.kwargs = kwargs
        QCoreApplication.postEvent(self, event_to_post)

    def event(self, event_to_handle: QEvent) -> bool:
        """
        Internal.
        Calls ``call_target``
        if ``event_to_handle`` is a :attr:`_call_request` event.

        :param ~PySide2.QtCore.PySide2.QtCore.QEvent event_to_handle:
            This event object
            should contain ``args`` and ``kwargs`` attributes
            that will be unpacked in the usual way
            before being forwarded to ``call_target``.

        Internal.
        For event handling in Qt event loop.

        Note that no forwarding occurs
        if ``self`` is destroyed
        before or while the event is processed here
        but after the event was posted.
        """
        if event_to_handle.type() != self._call_request:
            return super().event(event_to_handle)
        self._call_target(
            *event_to_handle.args, **event_to_handle.kwargs
        )
        return True
