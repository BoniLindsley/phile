#!/usr/bin/env python3
"""
-----------------------------------------------------------------
Convenience module for using :attr:`~watchdog.observers.Observer`
-----------------------------------------------------------------
"""

# Standard library.
import collections.abc
import contextlib
import pathlib

# External dependencies.
import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]


def was_start_called(
    observer: watchdog.observers.api.BaseObserver
) -> bool:
    """
    Returns whether
    the :meth:`~watchdog.observers.api.BaseObserver.start` method
    of ``observer`` was called.

    .. admonition:: Raison d'être

       This can be useful for avoiding :exc:`RuntimeError`.
       from calling :meth:`~threading.Thread.start` twice.
    """
    return observer.ident is not None


def was_stop_called(
    observer: watchdog.observers.api.BaseObserver
) -> bool:
    """
    Returns whether
    the :meth:`~watchdog.observers.api.BaseObserver.stop` method
    of ``observer`` was called.

    .. admonition:: Implementation detail

       Uses an implementation-specific work-around
       as it uses underscore variables.

    .. admonition:: Raison d'être

       The :meth:`~watchdog.observers.api.BaseObserver.stop` method
       occurs asynchronously,
       in the sense that :meth:`~threading.Thread.is_alive`
       may not be :data:`False` immediately
       after :meth:`~watchdog.observers.api.BaseObserver.stop` returns.
       This function on the other hand returns :data:`True`
       after such a call,
       hence the name of the function.

       Note that :meth:`~watchdog.observers.api.BaseObserver.stop`
       is idempotent.
       And it can be called before
       :meth:`~watchdog.observers.api.BaseObserver.start`,
       which will then try to stop it immediately.
       In particular, it is possible
       to have :func:`was_start_called` being :data:`False`
       while :func:`was_stop_called` being :data:`True`.
    """
    return observer._stopped_event.is_set()


@contextlib.contextmanager
def open(
    *args,
    opener=watchdog.observers.Observer,
    **kwargs
) -> collections.abc.Iterator[watchdog.observers.api.BaseObserver]:
    observer = opener(*args, **kwargs)
    try:
        observer.start()
        yield observer
    finally:
        observer.stop()


@contextlib.asynccontextmanager
async def async_open(
    *args,
    opener=watchdog.observers.Observer,
    **kwargs
) -> collections.abc.AsyncIterator[watchdog.observers.api.BaseObserver]:
    observer = opener(*args, **kwargs)
    try:
        observer.start()
        yield observer
    finally:
        observer.stop()


def has_handlers(
    observer: watchdog.observers.api.BaseObserver,
    watch: watchdog.observers.api.ObservedWatch
) -> bool:
    """
    Returns whether any handlers are monitoring ``watch``.

    .. admonition:: Implementation detail

       Uses an implementation-specific work-around
       as it uses underscore variables.
    """
    try:
        return bool(observer._handlers[watch])
    except KeyError:
        return False


def add_handler(
    observer: watchdog.observers.api.BaseObserver,
    event_handler: watchdog.events.FileSystemEventHandler,
    path: pathlib.Path,
    recursive: bool = False,
) -> watchdog.observers.api.ObservedWatch:
    """
    Notify ``event_handler`` of changes in ``path``.

    This function is identical
    to :meth:`~watchdog.observers.api.BaseObserver.schedule`,
    except the ``path`` parameter should be a :class:`~pathlib.Path`,
    for potential type checking purposes.
    This function is provided mainly for symmetry of operations
    with :func:`remove_handler`.

    .. admonition:: Raison d'être

       The :cls:`~watchdog.observers.api.BaseObserver` class
       provides :meth:`~watchdog.observers.api.BaseObserver.schedule`
       and
       :meth:`~watchdog.observers.api.BaseObserver.add_handler_for_watch`
       for registering ``event_handler`` to be called later.
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
       :meth:`~watchdog.observers.api.BaseObserver.add_handler_for_watch`
       so that the handler would not be registered against no monitoring
       except in simple use cases.
       Otherwise, if the user has to do their own redundant tracking
       of :attr:`~watchdog.observers.api.ObservedWatch.path`-s.
    """
    return observer.schedule(event_handler, str(path), recursive)


def remove_handler(
    observer: watchdog.observers.api.BaseObserver,
    event_handler: watchdog.events.FileSystemEventHandler,
    watch: watchdog.observers.api.ObservedWatch,
) -> None:
    """
    Stop notifying ``event_handler`` of changes in ``watch``.

    It merges
    :meth:`~watchdog.observers.api.BaseObserver.remove_handler_for_watch`
    and :meth:`~watchdog.observers.api.BaseObserver.unschedule`.
    Note that the ``path`` parameter should be a :class:`~pathlib.Path`,
    for potential type checking purposes.

    .. admonition:: Implementation detail

       This is an implementation-specific work-around
       as it uses underscore variables.

    .. admonition:: Raison d'être

       The :cls:`~watchdog.observers.api.BaseObserver` class
       provides :meth:`~watchdog.observers.api.BaseObserver.unschedule`
       and
       :meth:`~watchdog.observers.api.BaseObserver.remove_handler_for_watch`
       for deregistering ``event_handler``
       as being interested in monitoring ``watch``.

       The :meth:`~watchdog.observers.api.BaseObserver.unschedule` method
       unregisters all handlers registered for ``watch``, whereas
       :meth:`~watchdog.observers.api.BaseObserver.remove_handler_for_watch`
       removes a single handler
       but without checking if the monitoring should stop.
       The former does not provide fine control over unregistering
       whereas the latter potentially leads to a inotify watch leak.

       This function provides finer control in the sense that
       it stops the monitoring if there are no more handlers registered
       for the given ``watch```, bridging functionality gaps.
    """

    with observer._lock:
        handlers = observer._handlers.get(watch)
        if not handlers:
            return
        handlers.remove(event_handler)
        if not handlers:
            emitter = observer._emitter_for_watch[watch]
            del observer._handlers[watch]
            observer._remove_emitter(emitter)
            observer._watches.remove(watch)
