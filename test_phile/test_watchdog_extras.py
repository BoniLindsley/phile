#!/usr/bin/env python3
"""
--------------------------
Test phile.watchdog_extras
--------------------------
"""

# Standard library.
import pathlib
import logging
import tempfile
import unittest

# External dependencies.
import watchdog.events  # type: ignore[import]

# Internal packages.
from phile.watchdog_extras import Observer
from test_phile.threaded_mock import ThreadedMock

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


class TestObserver(unittest.TestCase):
    """Tests :class:`~phile.PySide2_extras.Observer`."""

    def setUp(self) -> None:
        """
        Create directories that observers use, and start the observer.

        The directories are recreated for each test
        to make sure no leftover files from tests
        would interfere with each other.
        """
        monitor_directory = tempfile.TemporaryDirectory()
        self.addCleanup(monitor_directory.cleanup)
        self.monitor_directory_path = pathlib.Path(
            monitor_directory.name
        )
        self.observer = Observer()
        self.addCleanup(self.observer.stop)

    def test_was_start_and_stop_called(self) -> None:
        """
        Ensure status methods get updated by start and stop.

        Also checks start and stop behaviours.
        """
        observer = self.observer
        self.assertTrue(not observer.was_start_called())
        self.assertTrue(not observer.is_alive())
        self.assertTrue(not observer.was_stop_called())
        _logger.debug('Starting observer.')
        observer.start()
        self.assertTrue(observer.was_start_called())
        self.assertTrue(observer.is_alive())
        self.assertTrue(not observer.was_stop_called())
        _logger.debug('Stopping observer.')
        # Stopping occurs asynchronously.
        # So we cannot determine whether it is alive or not.
        observer.stop()
        self.assertTrue(observer.was_start_called())
        self.assertTrue(observer.was_stop_called())

    def test_stop_unstarted_observer(self) -> None:
        """
        Stopping an unstarted observer prevents starting.

        More specifically, it starts, but immediately stops.
        """
        observer = self.observer
        self.assertTrue(not observer.was_start_called())
        self.assertTrue(not observer.is_alive())
        self.assertTrue(not observer.was_stop_called())
        _logger.debug('Stopping an unstarted observer.')
        observer.stop()
        self.assertTrue(not observer.was_start_called())
        self.assertTrue(not observer.is_alive())
        self.assertTrue(observer.was_stop_called())
        _logger.debug('Starting observer.')
        observer.start()
        self.assertTrue(observer.was_start_called())
        self.assertTrue(not observer.is_alive())
        self.assertTrue(observer.was_stop_called())

    def test_add_and_remove_and_has_handlers(self) -> None:
        """Adding and removing handlers do add handlers."""

        self.assertTrue(not self.observer.has_handlers())
        # Detect when the handler will be dispatched.
        event_handler = watchdog.events.FileSystemEventHandler()
        event_handler.dispatch = ThreadedMock(  # type: ignore
            wraps=event_handler.dispatch
        )
        # Creating a file inside the monitored directory
        # triggers an event dispatch to the handler.
        watch = self.observer.add_handler(
            event_handler, self.monitor_directory_path
        )
        self.assertTrue(self.observer.has_handlers())
        self.observer.start()
        new_file_path = self.monitor_directory_path / 'new_file'
        new_file_path.touch()
        event_handler.dispatch.assert_called_soon()

        # Try removing it.
        # Check that it is removed
        # by adding another handler and deleting the monitored file.
        # That should dispatch the new handler,
        # but the first one would not be dispatched if removed.
        # This uses the implementation detail that
        # handlers are called in the order they were added.
        old_event_handler = event_handler
        old_event_handler.dispatch.reset_mock()
        self.observer.remove_handler(old_event_handler, watch)
        self.assertTrue(not self.observer.has_handlers())
        event_handler = watchdog.events.FileSystemEventHandler()
        event_handler.dispatch = ThreadedMock(  # type: ignore
            wraps=event_handler.dispatch
        )
        watch = self.observer.add_handler(
            event_handler, self.monitor_directory_path
        )
        self.assertTrue(self.observer.has_handlers())
        new_file_path = self.monitor_directory_path / 'new_file'
        new_file_path.unlink()
        event_handler.dispatch.assert_called_soon()
        old_event_handler.dispatch.assert_not_called()

        # Clean-up.
        self.observer.remove_handler(event_handler, watch)


if __name__ == '__main__':
    unittest.main()
