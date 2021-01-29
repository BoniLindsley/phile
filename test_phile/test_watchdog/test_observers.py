#!/usr/bin/env python3
"""
-----------------------------------
Test :mod:`phile.watchdog.observer`
-----------------------------------
"""

# Standard library.
import pathlib
import tempfile
import unittest

# External dependencies.
import watchdog.events
import watchdog.observers
import watchdog.observers.polling

# Internal packages.
import phile.watchdog.observers


class UsesMonitorDirectory(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        monitor_directory = tempfile.TemporaryDirectory()
        self.addCleanup(monitor_directory.cleanup)
        self.monitor_directory_path = pathlib.Path(
            monitor_directory.name
        )


class UsesObserver(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.observer = watchdog.observers.Observer()
        self.addCleanup(self.observer.stop)


class TestWasStartCalled(UsesObserver, unittest.TestCase):
    """Tests :func:`~phile.watchdog.observers.was_start_called`."""

    def test_before_and_after_start(self) -> None:
        observer = self.observer
        self.assertFalse(
            phile.watchdog.observers.was_start_called(observer)
        )
        observer.start()
        self.assertTrue(
            phile.watchdog.observers.was_start_called(observer)
        )


class TestWasStopCalled(UsesObserver, unittest.TestCase):
    """Tests :func:`~phile.watchdog.observers.was_stop_called`."""

    def test_before_and_after_stop(self) -> None:
        observer = self.observer
        self.assertFalse(
            phile.watchdog.observers.was_stop_called(observer)
        )
        observer.stop()
        self.assertTrue(
            phile.watchdog.observers.was_stop_called(observer)
        )


class TestOpen(unittest.TestCase):
    """Tests :func:`~phile.watchdog.observers.open`."""

    def test_context_starts_and_stops(self) -> None:
        with phile.watchdog.observers.open() as observer:
            self.addCleanup(observer.stop)
            self.assertTrue(
                phile.watchdog.observers.was_start_called(observer)
            )
        self.assertTrue(
            phile.watchdog.observers.was_stop_called(observer)
        )

    def test_context_using_custom_opener(self) -> None:
        with phile.watchdog.observers.open(
            opener=watchdog.observers.polling.PollingObserver
        ) as observer:
            self.addCleanup(observer.stop)


class TestAsyncOpen(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.watchdog.observers.async_open`."""

    async def test_context_starts_and_stops(self) -> None:
        async with phile.watchdog.observers.async_open() as observer:
            self.addCleanup(observer.stop)
            self.assertTrue(
                phile.watchdog.observers.was_start_called(observer)
            )
        self.assertTrue(
            phile.watchdog.observers.was_stop_called(observer)
        )

    async def test_context_using_custom_opener(self) -> None:
        async with phile.watchdog.observers.async_open(
            opener=watchdog.observers.polling.PollingObserver
        ) as observer:
            self.addCleanup(observer.stop)


class TestHasHandlers(
    UsesMonitorDirectory, UsesObserver, unittest.TestCase
):
    """Tests :func:`~phile.watchdog.observers.has_handlers`."""

    def test_after_scheduling(self) -> None:
        observer = self.observer
        watch = watchdog.observers.api.ObservedWatch(
            path=str(self.monitor_directory_path), recursive=False
        )
        self.assertFalse(
            phile.watchdog.observers.has_handlers(observer, watch)
        )
        observer.schedule(
            event_handler=watchdog.events.FileSystemEventHandler(),
            path=str(self.monitor_directory_path),
        )
        self.assertTrue(
            phile.watchdog.observers.has_handlers(observer, watch)
        )

    def test_watch_with_wrong_recursive_should_fail(self) -> None:
        observer = self.observer
        observer.schedule(
            event_handler=watchdog.events.FileSystemEventHandler(),
            path=str(self.monitor_directory_path),
        )
        bad_watch = watchdog.observers.api.ObservedWatch(
            path=str(self.monitor_directory_path), recursive=True
        )
        self.assertFalse(
            phile.watchdog.observers.has_handlers(observer, bad_watch)
        )

    def test_after_unscheduling(self) -> None:
        observer = self.observer
        watch = observer.schedule(
            event_handler=watchdog.events.FileSystemEventHandler(),
            path=str(self.monitor_directory_path),
        )
        observer.unschedule(watch)
        self.assertFalse(
            phile.watchdog.observers.has_handlers(observer, watch)
        )


class TestAddHandler(
    UsesMonitorDirectory, UsesObserver, unittest.TestCase
):
    """Tests :func:`~phile.watchdog.observers.add_handler`."""

    def test_simple_add(self) -> None:
        observer = self.observer
        watch = phile.watchdog.observers.add_handler(
            observer=observer,
            event_handler=watchdog.events.FileSystemEventHandler(),
            path=self.monitor_directory_path,
        )
        self.assertTrue(
            phile.watchdog.observers.has_handlers(observer, watch)
        )


class TestRemoveHandler(
    UsesMonitorDirectory, UsesObserver, unittest.TestCase
):
    """Tests :func:`~phile.watchdog.observers.remove_handler`."""

    def test_raison_detre(self) -> None:
        observer = self.observer
        self.assertFalse(observer.emitters)
        event_handler = watchdog.events.FileSystemEventHandler()
        watch = observer.schedule(
            event_handler=event_handler,
            path=str(self.monitor_directory_path),
        )
        observer.remove_handler_for_watch(
            event_handler=event_handler,
            watch=watch,
        )
        self.assertFalse(
            phile.watchdog.observers.has_handlers(observer, watch)
        )
        self.assertTrue(
            observer.emitters,
            'May be resource leak is fixed'
            ' and `remove_handler` is not needed anymore?',
        )

    def test_removing_handler_removes_emitter(self) -> None:
        observer = self.observer
        event_handler = watchdog.events.FileSystemEventHandler()
        watch = observer.schedule(
            event_handler=event_handler,
            path=str(self.monitor_directory_path),
        )
        phile.watchdog.observers.remove_handler(
            observer=observer,
            event_handler=event_handler,
            watch=watch,
        )
        self.assertFalse(
            phile.watchdog.observers.has_handlers(observer, watch)
        )
        self.assertFalse(observer.emitters)

    def test_keep_emitter_if_watch_has_handlers_still(self) -> None:
        observer = self.observer
        event_handler = watchdog.events.FileSystemEventHandler()
        watch = observer.schedule(
            event_handler=event_handler,
            path=str(self.monitor_directory_path),
        )
        watch = observer.schedule(
            event_handler=watchdog.events.FileSystemEventHandler(),
            path=str(self.monitor_directory_path),
        )
        phile.watchdog.observers.remove_handler(
            observer=observer,
            event_handler=event_handler,
            watch=watch,
        )
        self.assertTrue(
            phile.watchdog.observers.has_handlers(observer, watch)
        )
        self.assertTrue(observer.emitters)

    def test_removing_non_existent_handler_does_nothing(self) -> None:
        observer = self.observer
        event_handler = watchdog.events.FileSystemEventHandler()
        watch = watchdog.observers.api.ObservedWatch(
            path=str(self.monitor_directory_path), recursive=False
        )
        phile.watchdog.observers.remove_handler(
            observer=observer,
            event_handler=event_handler,
            watch=watch,
        )
        self.assertFalse(
            phile.watchdog.observers.has_handlers(observer, watch)
        )
