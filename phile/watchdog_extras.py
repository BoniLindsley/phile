#!/usr/bin/env python3
"""
-------------------------
watchdog observer wrapper
-------------------------
"""

# Standard library.
import pathlib

# External dependencies.
import watchdog.events  # type: ignore
import watchdog.observers  # type: ignore


class Observer(watchdog.observers.Observer):
    """
    Monitors for file system events and notify interested handlers.

    .. admonition:: Raison d'être

       The parent class :attr:`~watchdog.observers.Observer`
       provides :meth:`~watchdog.observers.api.BaseObserver.schedule`
       and
       :meth:`~watchdog.observers.api.BaseObserver.add_handler_for_watch`
       for registering,
       and :meth:`~watchdog.observers.api.BaseObserver.unschedule` and
       :meth:`~watchdog.observers.api.BaseObserver.remove_handler_for_watch`
       for deregistering,
       as being interested in certain file or directory changes.

       The :meth:`~watchdog.observers.api.BaseObserver.schedule` method
       sets up file monitoring of the given ``path``,
       and remembers which handlers to call for the ``path``.
       The
       :meth:`~watchdog.observers.api.BaseObserver.add_handler_for_watch`
       method does the same except it does not do the setting up.
       For predictability reasons,
       since :meth:`~watchdog.observers.api.BaseObserver.schedule`
       skips the setting up if its was already done,
       it should always be used over
       :meth:`~watchdog.observers.api.BaseObserver.add_handler_for_watch`,
       otherwise the handler may be registered against no monitoring
       except in simple use cases,
       or if the user does their own redundant tracking
       of :attr:`~watchdog.observers.api.ObservedWatch.path`-s.

       On the clean-up end,
       the :meth:`~watchdog.observers.api.BaseObserver.unschedule` method
       unregisters all handlers registered for a given
       :class:`~watchdog.observers.api.ObservedWatch`
       and stops monitoring the associated ``path``. whereas
       :meth:`~watchdog.observers.api.BaseObserver.remove_handler_for_watch`
       removes a single handler
       but without checking if the monitoring should stop.
       The former does not provide fine control over unregistering
       whereas the latter potentially leads to a inotify watch leak.

    This class introduces the :meth:`add_handler`
    and :meth:`remove_handler` methods.
    The latter provides finer control in the sense that
    it stops the monitoring if there are no more handlers registered
    for the given :class:`~watchdog.observers.api.ObservedWatch`.
    bridging functionality gaps
    in :attr:`~watchdog.observers.Observer`.
    It also ignores removal attempts after the observer is stopped.
    The former is identical
    to :meth:`~watchdog.observers.api.BaseObserver.schedule`,
    provided mainly for symmetry of operations,
    except the ``path`` parameter should be a :class:`~pathlib.Path`,
    for potential type checking purposes.

    This class also introduces :meth:`was_start_called`
    and :meth:`was_stop_called`
    to determine the status of the :class:`Observer`.
    They are sometimes useful in determining
    whether an :class:`Observer`
    can be :meth:`~watchdog.observers.api.BaseObserver.start`-ed
    since :meth:`~threading.Thread.start`-ing
    a :class:`~threading.Thread` twice raises an exception.
    """

    def __init__(self, *args, **kwargs):
        """
        Forwards all arguments
        to :attr:`~watchdog.observers.Observer`.

        The underlying :class:`~threading.Thread`
        is set as a :attr:`~threading.Thread.daemon`
        as the file monitoring does not require any mandatory clean-up.
        """
        super().__init__(*args, **kwargs)
        self.daemon = True

    def add_handler(
        self,
        event_handler: watchdog.events.FileSystemEventHandler,
        path: pathlib.Path,
        recursive: bool = False,
    ) -> watchdog.observers.api.ObservedWatch:
        """Notify ``event_handler`` of changes in ``path``."""
        return self.schedule(event_handler, str(path), recursive)

    def has_handlers(self) -> bool:
        return bool(self._handlers)

    def remove_handler(
        self, event_handler: watchdog.events.FileSystemEventHandler,
        watch: watchdog.observers.api.ObservedWatch
    ) -> None:
        """
        Stop notifying ``event_handler`` of changes in ``watch``.

        This is an implementation-specific work-around
        as it uses underscore variables.
        It merges
        :meth:`~watchdog.observers.api.BaseObserver.remove_handler_for_watch`
        and :meth:`~watchdog.observers.api.BaseObserver.unschedule`.
        """
        with self._lock:
            handlers = self._handlers.get(watch)
            if not handlers:
                return
            handlers.remove(event_handler)
            if not handlers:
                emitter = self._emitter_for_watch[watch]
                del self._handlers[watch]
                self._remove_emitter(emitter)
                self._watches.remove(watch)

    def was_start_called(self) -> bool:
        return self.ident is not None

    def was_stop_called(self) -> bool:
        return self._stopped_event.is_set()
