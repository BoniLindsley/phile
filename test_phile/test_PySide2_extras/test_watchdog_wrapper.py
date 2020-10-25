#!/usr/bin/env python3
"""
------------------------------------------
Test phile.PySide2_extras.watchdog_wrapper
------------------------------------------
"""

# Standard library.
import pathlib
import logging
import tempfile
import unittest
import unittest.mock

# External dependencies.
from PySide2.QtCore import QObject
from PySide2.QtGui import QShowEvent
import watchdog.events  # type: ignore

# Internal packages.
from phile.PySide2_extras.watchdog_wrapper import (
    FileSystemMonitor, FileSystemSignalEmitter
)
from phile.watchdog_extras import Observer
from test_phile.pyside2_test_tools import QTestApplication
from test_phile.threaded_mock import ThreadedMock

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


class TestFileSystemSignalEmitter(unittest.TestCase):
    """Tests :class:`~phile.PySide2_extras.FileSystemSignalEmitter`."""

    def setUp(self) -> None:
        """
        Create a PySide2 application before each method test.

        It has to be created to do initialisation
        for GUI widgets to work.
        A new one is created for each test
        to make sure no application state information
        would interfere with each other.
        """
        monitor_directory = tempfile.TemporaryDirectory()
        self.addCleanup(monitor_directory.cleanup)
        self.monitor_directory_path = pathlib.Path(
            monitor_directory.name
        )
        self.app = QTestApplication()
        self.addCleanup(self.app.tear_down)
        self.signal_emitter = FileSystemSignalEmitter(
            monitored_path=self.monitor_directory_path
        )
        self.addCleanup(self.signal_emitter.deleteLater)

    def test_constructor(self) -> None:
        """
        Create the signal emitter.

        The emitter is created in `setUp` and deleted in `tearDown`.
        This "empty" test flags up any potential issues
        with the constructor that would affect other tests too.
        """

    def test_dispatch_emits_signal(self) -> None:
        """Dispatch forwards watchdog events to a signal."""
        signal_catcher = unittest.mock.Mock()
        signal_emitter = self.signal_emitter
        signal = signal_emitter.file_system_event_detected
        signal.connect(signal_catcher)  # type: ignore
        signal_emitter.dispatch(
            watchdog.events.FileCreatedEvent(
                str(self.monitor_directory_path)
            )
        )
        self.app.process_events()
        self.assertTrue(signal_catcher.called)

    def test_ignores_other_events(self) -> None:
        """Event handling should only process watchdog events."""
        signal_catcher = unittest.mock.Mock()
        signal_emitter = self.signal_emitter
        signal = signal_emitter.file_system_event_detected
        signal.connect(signal_catcher)  # type: ignore
        signal_emitter.event(QShowEvent())
        self.app.process_events()
        self.assertTrue(not signal_catcher.called)

    def test_start_failing_with_non_monitor_parent(self) -> None:
        """
        Emitter cannot start without observer if parent is not a monitor.
        """
        fake_parent = QObject()
        self.signal_emitter.setParent(fake_parent)
        with self.assertRaises(RuntimeError):
            self.signal_emitter.start()
        fake_parent.deleteLater()

    def test_start_twice(self) -> None:
        """
        Emitters can be started twice without stopping first.
        """
        observer = Observer()
        self.signal_emitter.start(_monitoring_observer=observer)
        self.assertTrue(self.signal_emitter.is_started())
        self.signal_emitter.start(_monitoring_observer=observer)
        self.assertTrue(self.signal_emitter.is_started())

    def test_start_with_custom_observer(self) -> None:
        """Emitter can be started by giving it an observer."""
        monitor_directory_path = self.monitor_directory_path
        # Create an observer to dispatch to the emitter.
        observer = Observer()
        observer.start()
        # Connect to the signal to detect whether it gets emiteed.
        signal_catcher = unittest.mock.Mock()
        signal_emitter = self.signal_emitter
        signal = signal_emitter.file_system_event_detected
        signal.connect(signal_catcher)  # type: ignore
        # Let the observer know about the emitter.
        self.signal_emitter.start(_monitoring_observer=observer)
        # Detect when the handler from main window will be dispatched.
        signal_emitter.dispatch = ThreadedMock(  # type: ignore
            target=signal_emitter.dispatch
        )
        # Dispatch an event to both handlers.
        # Wait until the second handler is called.
        # We can be reasonably sure the first handler is dispatched
        # at that point.
        new_file_path = monitor_directory_path / 'new_file'
        new_file_path.touch()
        signal_emitter.dispatch.assert_called_soon()
        # Check that the first handler is dispatched
        # which should emit a signal
        # which is connected to the signal catcher mock.
        self.app.process_events()
        self.assertTrue(signal_catcher.called)
        # Clean-up.
        self.signal_emitter.stop()
        observer.stop()


class TestFileSystemMonitor(unittest.TestCase):
    """Tests :class:`~phile.PySide2_extras.FileSystemMonitor."""

    def setUp(self) -> None:
        """
        Create a PySide2 application before each method test.

        It has to be created to do initialisation
        for GUI widgets to work.
        A new one is created for each test
        to make sure no application state information
        would interfere with each other.
        """
        monitor_directory = tempfile.TemporaryDirectory()
        self.addCleanup(monitor_directory.cleanup)
        self.monitor_directory_path = pathlib.Path(
            monitor_directory.name
        )
        self.app = QTestApplication()
        self.addCleanup(self.app.tear_down)
        self.monitor = FileSystemMonitor()
        # Allow posix_signal to be deleted in unit tests.
        # They can create an arbitrary QObject to fake a clean-up.
        self.addCleanup(lambda: self.monitor.deleteLater())

    def test_construct_and_delete(self) -> None:
        """
        Create the event monitor.

        The monitor is created in `setUp` and deleted in `tearDown`.
        This "empty" test flags up any potential issues
        with the constructor that would affect other tests too.
        """
        self.assertTrue(not self.monitor.was_start_called())
        self.assertTrue(not self.monitor.was_stop_called())

    def test_constructor_with_custom_observer(self) -> None:
        """Monitor can be given a custom observer."""
        observer = Observer()
        monitor = FileSystemMonitor(_watchdog_observer=observer)
        monitor.start()
        self.assertTrue(observer.was_start_called())
        monitor.stop()
        self.assertTrue(observer.was_stop_called())
        monitor.deleteLater()

    def test_was_start_and_stop_called(self) -> None:
        """Calls to `start` and `stop` should change `is_started`."""
        _logger.debug('Starting monitor.')
        self.monitor.start()
        self.assertTrue(self.monitor.was_start_called())
        self.assertTrue(not self.monitor.was_stop_called())
        _logger.debug('Stopping monitor.')
        self.monitor.stop()
        self.assertTrue(self.monitor.was_start_called())
        self.assertTrue(self.monitor.was_stop_called())

    def test_start_twice(self) -> None:
        """Starting monitor twice is okay if not stopped yet."""
        _logger.debug('Starting monitor.')
        self.monitor.start()
        self.assertTrue(self.monitor.was_start_called())
        self.assertTrue(not self.monitor.was_stop_called())
        _logger.debug('Re-starting monitor.')
        self.monitor.start()
        self.assertTrue(self.monitor.was_start_called())
        self.assertTrue(not self.monitor.was_stop_called())

    def test_stop_twice(self) -> None:
        """Stopping a monitor twice is okay."""
        _logger.debug('Starting monitor.')
        self.monitor.start()
        self.assertTrue(self.monitor.was_start_called())
        self.assertTrue(not self.monitor.was_stop_called())
        _logger.debug('Stopping monitor.')
        self.monitor.stop()
        self.assertTrue(self.monitor.was_start_called())
        self.assertTrue(self.monitor.was_stop_called())
        _logger.debug('Re-stopping monitor.')
        self.monitor.stop()
        self.assertTrue(self.monitor.was_start_called())
        self.assertTrue(self.monitor.was_stop_called())

    def test_start_stopped_monitor(self) -> None:
        """Cannot start monitor if already stopped.."""
        _logger.debug('Starting monitor.')
        self.monitor.start()
        self.assertTrue(self.monitor.was_start_called())
        self.assertTrue(not self.monitor.was_stop_called())
        _logger.debug('Stopping monitor.')
        self.monitor.stop()
        self.assertTrue(self.monitor.was_start_called())
        self.assertTrue(self.monitor.was_stop_called())
        _logger.debug('Re-starting monitor.')
        with self.assertRaises(RuntimeError):
            self.monitor.start()

    def test_stop_unstarted_monitor(self) -> None:
        """Cannot stop monitor if not started."""
        _logger.debug('Stopping monitor.')
        with self.assertRaises(RuntimeError):
            self.monitor.stop()

    def test_delete_stopping_child(self) -> None:
        """
        Gracefully delete even if the monitor still has child emitters.

        Emitters that are started and not started should both be deleted.
        """
        _logger.debug('Creating child emitter to start.')
        started_emitter = FileSystemSignalEmitter(
            self.monitor, monitored_path=self.monitor_directory_path
        )
        observer = self.monitor._watchdog_observer
        self.assertTrue(not observer.has_handlers())
        started_emitter.start()
        self.assertTrue(observer.has_handlers())
        _logger.debug('Creating child emitter that will not be started.')
        unstarted_emitter = FileSystemSignalEmitter(
            self.monitor, monitored_path=self.monitor_directory_path
        )
        _logger.debug('Deleting monitor.')
        self.monitor.deleteLater()
        self.monitor = QObject()  # Give `tearDown` an object to delete.
        self.app.process_deferred_delete_events()
        _logger.debug('Attempting to access destructed emitters.')
        with self.assertRaises(RuntimeError):
            started_emitter.children()
        with self.assertRaises(RuntimeError):
            unstarted_emitter.children()
        # Observer reference was kept alive, even if the monitor is gone.
        self.assertTrue(not observer.has_handlers())

    def test_start_starts_and_stop_stops_child(self) -> None:
        """Starting monitor should start any attached children."""
        _logger.debug('Creating child emitter to be started.')
        signal_emitter = FileSystemSignalEmitter(
            self.monitor, monitored_path=self.monitor_directory_path
        )
        observer = self.monitor._watchdog_observer
        self.assertTrue(not observer.has_handlers())
        _logger.debug('Starting monitor.')
        self.monitor.start()
        self.assertTrue(signal_emitter.is_started())
        self.assertTrue(observer.has_handlers())
        _logger.debug('Creating child emitter that will not be started.')
        signal_emitter_2 = FileSystemSignalEmitter(
            self.monitor, monitored_path=self.monitor_directory_path
        )
        _logger.debug(not signal_emitter_2.is_started())
        _logger.debug('Stopping monitor.')
        self.monitor.stop()
        self.assertTrue(not signal_emitter.is_started())
        self.assertTrue(not signal_emitter_2.is_started())
        self.assertTrue(not observer.has_handlers())

    def test_delete_and_stop_child(self) -> None:
        """
        Child emitters can be stopped and deleted safely.

        This centres around calling child methods.
        """
        _logger.debug('Creating child to be started and stopped.')
        stop_emitter = FileSystemSignalEmitter(
            self.monitor, monitored_path=self.monitor_directory_path
        )
        observer = self.monitor._watchdog_observer
        self.assertTrue(not observer.has_handlers())
        _logger.debug('Creating child to be started and deleted.')
        delete_emitter = FileSystemSignalEmitter(
            self.monitor, monitored_path=self.monitor_directory_path
        )
        self.assertTrue(not observer.has_handlers())
        _logger.debug('Starting both child emitters.')
        stop_emitter.start()
        self.assertTrue(observer.has_handlers())
        self.assertTrue(stop_emitter.is_started())
        delete_emitter.start()
        self.assertTrue(delete_emitter.is_started())
        self.assertTrue(observer.has_handlers())
        _logger.debug('Stopping one of the child.')
        stop_emitter.stop()
        self.assertTrue(not stop_emitter.is_started())
        self.assertTrue(observer.has_handlers())
        _logger.debug('Deleting the other child.')
        delete_emitter.deleteLater()
        self.app.process_deferred_delete_events()
        self.assertListEqual(self.monitor.children(), [stop_emitter])
        self.assertTrue(not observer.has_handlers())

    def test_start_starting_child_with_explicit_set_parent(self) -> None:
        """Emitters can set monitor as parent explicitly."""
        emitter = FileSystemSignalEmitter(
            monitored_path=self.monitor_directory_path
        )
        emitter.setParent(self.monitor)
        self.monitor.start()
        self.assertTrue(emitter.is_started())

    def test_ignoring_children_that_are_not_emitters(self) -> None:
        """Monitors can have children that are not emitters."""
        fake_child = QObject()
        fake_child.setParent(self.monitor)
        self.monitor.start()
        self.assertTrue(self.monitor.was_start_called())
        self.monitor.stop()
        self.assertTrue(self.monitor.was_stop_called())

    def test_start_ignoring_started_children(self) -> None:
        """Monitors can start even with started children."""
        emitter = FileSystemSignalEmitter(
            monitored_path=self.monitor_directory_path
        )
        emitter.setParent(self.monitor)
        emitter.start()
        self.assertTrue(emitter.is_started())
        self.monitor.start()
        self.assertTrue(self.monitor.was_start_called())
        emitter.stop()
        self.assertTrue(not emitter.is_started())
        self.monitor.stop()
        self.assertTrue(self.monitor.was_stop_called())

    def test_start_and_unparent_child(self) -> None:
        """
        Add an emitter as child, and then unparent it.

        This is to ensure that parent changes do not raise errors.
        """
        _logger.debug('Creating child emitter.')
        signal_emitter = FileSystemSignalEmitter(
            self.monitor, monitored_path=self.monitor_directory_path
        )
        observer = self.monitor._watchdog_observer
        self.assertTrue(not observer.has_handlers())
        _logger.debug('Starting monitor.')
        signal_emitter.start()
        self.assertTrue(observer.has_handlers())
        _logger.debug('Unparenting emitter.')
        fake_parent = QObject()
        signal_emitter.setParent(fake_parent)
        self.assertEqual(len(self.monitor.children()), 0)
        self.assertTrue(not observer.has_handlers())
        _logger.debug('Deleting emitter to clean-up.')
        fake_parent.deleteLater()
        _logger.debug('Ending test.')


if __name__ == '__main__':
    unittest.main()
