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
import unittest.mock

# External dependencies.
import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]

# Internal packages.
import phile.watchdog_extras
import test_phile.threaded_mock

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


class TestEventHandler(unittest.TestCase):
    """Tests :data:`~phile.watchdog_extras.EventHandler`."""

    def test_lambda(self) -> None:
        """
        A lambda can be a :data:`~phile.watchdog_extras.EventHandler`.
        """
        _: phile.watchdog_extras.EventHandler = lambda _: None

    def test_function(self) -> None:
        """
        A function can be a :data:`~phile.watchdog_extras.EventHandler`.
        """

        def event_handle_function(
            event: watchdog.events.FileSystemEvent
        ) -> None:
            pass

        _: phile.watchdog_extras.EventHandler = event_handle_function


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
        self.observer = phile.watchdog_extras.Observer()
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
        # So we cannot determine whether it is alive without joining.
        # We want to avoid joining since it is slow.
        # And testing `is_alive` would just be testing `Threading.thread`
        # stopping behaviour which is a little unnecessary.
        observer.stop()
        self.assertTrue(observer.was_start_called())
        self.assertTrue(observer.was_stop_called())

    def test_stop_unstarted_observer(self) -> None:
        """
        Stopping an unstarted observer prevents starting.

        More specifically, it starts, but immediately stops.
        The ``was_*_called`` methods should still report appropriately,
        as their names suggest.
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
        """Adding and removing handlers do add and remove handlers."""
        self.assertTrue(not self.observer.has_handlers())
        # Detect when the handler will be dispatched.
        # This is to check that adding does add the handler.
        handler_dispatch_patcher = unittest.mock.patch(
            'watchdog.events.FileSystemEventHandler.dispatch',
            new_callable=test_phile.threaded_mock.ThreadedMock,
        )
        handler_dispatch_patcher_mock = handler_dispatch_patcher.start()
        self.addCleanup(handler_dispatch_patcher.stop)
        # Add handler.
        event_handler = watchdog.events.FileSystemEventHandler()
        watch = self.observer.add_handler(
            event_handler, self.monitor_directory_path
        )
        self.assertTrue(self.observer.has_handlers())
        # Creating a file inside the monitored directory
        # triggers an event dispatch to the handler.
        self.observer.start()
        event_handler.dispatch.assert_not_called()
        (self.monitor_directory_path / 'new_file').touch()
        event_handler.dispatch.assert_called_soon()
        # Remove the handler and check that status is reflected as such.
        self.observer.remove_handler(event_handler, watch)
        self.assertTrue(not self.observer.has_handlers())

    def test_remove_unadded_handler(self) -> None:
        """Ignore remove request for handlers that were not added."""
        event_handler = watchdog.events.FileSystemEventHandler()
        watch = watchdog.observers.api.ObservedWatch(
            path=str(self.monitor_directory_path), recursive=False
        )
        self.observer.remove_handler(event_handler, watch)
        self.assertTrue(not self.observer.has_handlers())

    def test_remove_only_one_of_two_handlers(self) -> None:
        """Removing some handlers should not remove all of them."""
        # Add handlers.
        event_handler = watchdog.events.FileSystemEventHandler()
        watch = self.observer.add_handler(
            event_handler, self.monitor_directory_path
        )
        # Add extra handler.
        self.observer.add_handler(
            watchdog.events.FileSystemEventHandler(),
            self.monitor_directory_path
        )
        # Removing the first handler should not remove the second one.
        self.assertTrue(self.observer.has_handlers())
        self.observer.remove_handler(event_handler, watch)
        self.assertTrue(self.observer.has_handlers())


class TestDispatcher(unittest.TestCase):
    """Unit test for :class:`~phile.PySide2_extras.Dispatcher`."""

    def setUp(self) -> None:
        """Create a handler to forward to."""
        self.event_handler = unittest.mock.Mock()
        self.dispatcher = phile.watchdog_extras.Dispatcher(
            event_handler=self.event_handler
        )

    def test_dispatch(self) -> None:
        """Dispatching calls the given handler."""
        event_to_dispatch = watchdog.events.FileCreatedEvent(None)
        self.dispatcher.dispatch(event_to_dispatch)
        self.event_handler.assert_called_with(event_to_dispatch)


def has_handlers(
    target_observer: watchdog.observers.Observer,
    watch_to_check: watchdog.observers.api.ObservedWatch
) -> bool:
    return target_observer._handlers.get(watch_to_check) is not None


class TestScheduler(unittest.TestCase):
    """Unit test for :class:`~phile.watchdog_extras.Scheduler`."""

    def setUp(self) -> None:
        """Create a handler to forward to."""
        self.observer = watchdog.observers.Observer()
        self.addCleanup(self.observer.stop)
        self.watched_path = pathlib.Path()
        self.scheduler = phile.watchdog_extras.Scheduler(
            watchdog_handler=unittest.mock.Mock(),
            watched_path=self.watched_path,
            watching_observer=self.observer,
        )
        self.watchdog_watch = self.scheduler._watchdog_watch

    def test_schedule_and_unschedule_and_is_scheduled(self) -> None:
        """Dispatching calls the given handler."""
        self.assertFalse(self.scheduler.is_scheduled())
        self.assertFalse(
            has_handlers(self.observer, self.watchdog_watch)
        )
        self.scheduler.schedule()
        self.assertTrue(self.scheduler.is_scheduled())
        self.assertTrue(has_handlers(self.observer, self.watchdog_watch))
        self.scheduler.unschedule()
        self.assertFalse(self.scheduler.is_scheduled())
        self.assertFalse(
            has_handlers(self.observer, self.watchdog_watch)
        )

    def test_sheduled_when_already_scheduled(self) -> None:
        """Scheduling a second time gets ignored."""
        self.scheduler.schedule()
        self.scheduler.schedule()

    def test_unsheduled_without_scheduling(self) -> None:
        """Unscheduling an unscheduled handle gets ignored"""
        self.scheduler.unschedule()

    def test_unschedule_with_other_handlers(self) -> None:
        """Do not remove emitter when there are other handlers."""
        other_scheduler = phile.watchdog_extras.Scheduler(
            watchdog_handler=unittest.mock.Mock(),
            watched_path=self.watched_path,
            watching_observer=self.observer,
        )
        other_scheduler.schedule()
        self.scheduler.schedule()
        self.assertTrue(has_handlers(self.observer, self.watchdog_watch))
        self.scheduler.unschedule()
        self.assertTrue(has_handlers(self.observer, self.watchdog_watch))

    def test_unschedule_manually_unscheduled_handler(self) -> None:
        """
        Unschedule manually unschedule handler should be fine.

        Already satisfied the postcondition of being unscheduled.
        So just say it is succeeded.
        """
        self.scheduler.schedule()
        self.assertTrue(has_handlers(self.observer, self.watchdog_watch))
        self.observer.unschedule(self.watchdog_watch)
        self.assertFalse(
            has_handlers(self.observer, self.watchdog_watch)
        )
        self.scheduler.unschedule()
        self.assertFalse(
            has_handlers(self.observer, self.watchdog_watch)
        )


if __name__ == '__main__':
    unittest.main()
