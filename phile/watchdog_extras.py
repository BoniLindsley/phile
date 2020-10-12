#!/usr/bin/env python3

# Standard library.
import pathlib

# External dependencies.
import watchdog.events  # type: ignore
import watchdog.observers  # type: ignore


class Observer(watchdog.observers.Observer):
    """
    Monitors for file system events and notify interested handlers.

    The underlying thread is set as a daemon
    as the file monitoring does not require any mandatory clean-up.

    This class provides some convenient addition to make it easier
    to use in conjunction with PySide2.

    The parent class `watchdog.observers.Observer`
    provides `schedule` and `add_handler_for_watch` for registering,
    and `unschedule` and `remove_handler_for_watch` for deregistering,
    as being interested in certain file or directory changes.

    The `schedule` method sets up file monitoring of the given `path`,
    and remembers which handlers to call for the `path`.
    The `add_handler_for_watch` does the same
    except it does not do the setting up.
    For predictability reasons,
    since `schedule` skips the setting up if its was already done,
    it should always be used over `add_handler_for_watch`,
    otherwise the handler may be registered against no monitoring
    except in simple use cases,
    or if the user does their own redundant tracking of `watch`-ed paths.

    On the clean-up end, the `unschedule` method unregisters
    all handlers registered for a given `watch`
    and stops monitoring the associated `path`.
    whereas the `remove_handler_for_watch` removes a single handler
    but without checking if the monitoring should stop.
    The former does not provide fine control over unregistering
    whereas the latter potentially leads to a inotify watch leak.

    This class introduces `add_handler` and `remove_handler` methods.
    The latter provides finer control in the sense that
    it stops the monitoring if there are no more handlers
    registered for the given `watch`,
    bridging the functionality gap.
    It also ignores removal attempts after the observer is stopped.
    The former is identical to `schedule`,
    provided mainly for symmetry of operations,
    except that the `path` parameter should be a `Pathlib.Path`,
    for potential type checking purposes.

    This class also introduces `was_start_called` and `was_start_called`
    to determine the status of the `Observer`.
    They are sometimes useful in determining
    whether an `Observer` can be `start`-ed
    since `start`-ing a `thread` twice raises an exception.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon = True

    def add_handler(
        self,
        event_handler: watchdog.events.FileSystemEventHandler,
        path: pathlib.Path,
        recursive: bool = False,
    ) -> watchdog.observers.api.ObservedWatch:
        """Notify `event_handler` of changes in `path`."""
        return self.schedule(event_handler, str(path), recursive)

    def has_handlers(self) -> bool:
        return bool(self._handlers)

    def remove_handler(
        self, event_handler: watchdog.events.FileSystemEventHandler,
        watch: watchdog.observers.api.ObservedWatch
    ) -> None:
        """
        Stop notifying`event_handler` of changes in `watch`.

        This is an implementation-specific work-around
        as it uses underscore variables.
        It merges `remove_handler_for_watch` with `unschedule`.
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
