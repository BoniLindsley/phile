#!/usr/bin/env python3
"""
------------------------------
test_phile.watchdog_test_tools
------------------------------
"""

# Standard library.
import logging
import threading

# External dependencies.
import watchdog.events  # type: ignore

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


class EventSetter(
    watchdog.events.FileSystemEventHandler, threading.Event
):
    """
    A watchdog event handler that sets a flag when dispatching.

    This is useful for confirming that events for a watchdog watch
    has been dispatched.
    Using the watchdog implementation detail
    that handlers are dispatched in the order they were added,
    by adding this as a handler last,
    it is possible to wait for other dispatchers to be called
    by waiting on this handler.

    Example::

        observer = Observer()
        observer.schedule(some_other_handler, monitored_path)
        setter = EventSetter()
        observer.schedule(setter, monitored_path)
        do_something_in(monitored_path)
        setter.wait()  # Add a timeout if necessary.
        # We can be reasonably sure that
        # the other handler has been dispatched.

    This is particularly useful in unit testing
    when it is not desirable to be intrusive with other handlers.
    """

    def dispatch(self, event: watchdog.events.FileSystemEvent):
        """Set the member event flag to signal the dispatch."""
        _logger.debug('EventSetter is dispatched.')
        self.set()
