#!/usr/bin/env python3
"""
--------------------------
Test phile.watchdog_extras
--------------------------
"""

# Standard library.
import dataclasses
import pathlib
import logging
import tempfile
import typing
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

IntCallback = (phile.watchdog_extras.SingleParameterCallback[int, None])


class TestSingleParameterCallback(unittest.TestCase):
    """Tests :data:`~phile.watchdog_extras.SingleParameterCallback`."""

    def do_callback_test(self, callback: IntCallback) -> None:
        """
        Calls ``callback`` directly and as a member.

        Call signature also checks the given ``callback`` in ``mypy``.
        """

        callback(0)

        @dataclasses.dataclass
        class Parent:
            callback: IntCallback

        self.parent = Parent(callback=callback)
        self.parent.callback(0)

    def test_class_method(self) -> None:
        """Methods of with proper parameter satisfies the protocol."""

        class IntObject:

            @classmethod
            def int_method(self, _: int) -> None:
                pass

        self.do_callback_test(IntObject.int_method)

    def test_function(self) -> None:
        """Subclass of protocol can inherit methods to satisfy it."""

        def int_function(_: int) -> None:
            pass

        self.do_callback_test(int_function)

    def test_lambda(self) -> None:
        """Lambda without signature satisfies protocol."""
        self.do_callback_test(lambda _: None)

    def test_method(self) -> None:
        """Methods of with proper parameter satisfies the protocol."""

        class IntObject:

            def int_method(self, _: int) -> None:
                pass

        self.do_callback_test(IntObject().int_method)

    def test_static_method(self) -> None:
        """Methods of with proper parameter satisfies the protocol."""

        class IntObject:

            @staticmethod
            def int_method(_: int) -> None:
                pass

        self.do_callback_test(IntObject.int_method)

    def test_subclass(self) -> None:
        """Subclass of protocol can inherit methods to satisfy it."""

        class Callback(IntCallback):
            pass

        self.do_callback_test(Callback())


class TestEventHandler(unittest.TestCase):
    """Tests :data:`~phile.watchdog_extras.EventHandler`."""

    def test_function(self) -> None:
        """
        A function can be a :data:`~phile.watchdog_extras.EventHandler`.
        """

        def event_handle_function(
            event: watchdog.events.FileSystemEvent
        ) -> None:
            pass

        _: phile.watchdog_extras.EventHandler = event_handle_function


class TestPathFilter(unittest.TestCase):
    """Tests :data:`~phile.watchdog_extras.PathFilter`."""

    def test_function(self) -> None:
        """
        A function can be a :data:`~phile.watchdog_extras.PathFilter`.
        """

        def path_handle_function(path: pathlib.Path) -> bool:
            return True

        path_filter: phile.watchdog_extras.PathFilter = (
            path_handle_function
        )
        self.assertTrue(path_filter(pathlib.Path()))


class TestPathHandler(unittest.TestCase):
    """Tests :data:`~phile.watchdog_extras.PathHandler`."""

    def test_function(self) -> None:
        """
        A function can be a :data:`~phile.watchdog_extras.PathHandler`.
        """

        def path_handle_function(path: pathlib.Path) -> None:
            pass

        handler: phile.watchdog_extras.PathHandler = (
            path_handle_function
        )
        handler(pathlib.Path())


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


def has_handlers(
    target_observer: watchdog.observers.Observer,
    watch_to_check: watchdog.observers.api.ObservedWatch
) -> bool:
    return target_observer._handlers.get(watch_to_check) is not None


class TestScheduler(unittest.TestCase):
    """Unit test for :class:`~phile.watchdog_extras.Scheduler`."""

    def setUp(self) -> None:
        """Create a handler to forward to."""
        self.observer = observer = watchdog.observers.Observer()
        self.addCleanup(self.observer.stop)
        self.watched_path = watched_path = pathlib.Path()
        self.path_filter = path_filter = unittest.mock.Mock()
        self.path_handler = path_handler = unittest.mock.Mock()
        self.scheduler = phile.watchdog_extras.Scheduler(
            path_filter=path_filter,
            path_handler=path_handler,
            watched_path=watched_path,
            watching_observer=observer,
        )

    def test_init_with_path_and_observer(self) -> None:
        """
        Provides a constructor without callbacks.

        So that other properties can be provided later,
        making the constructor less of a mess.
        Observer and paths are mandatory
        since creating a new constructor
        means creating a possibly unused thread
        and there is no good default paths to use as a default.
        """
        other_scheduler = phile.watchdog_extras.Scheduler(
            watched_path=self.watched_path,
            watching_observer=self.observer,
        )
        file_path = pathlib.Path('created')
        source_event = watchdog.events.FileCreatedEvent(str(file_path))
        other_scheduler.dispatch(source_event)

    def test_is_scheduled(self) -> None:
        """Dispatching calls the given handler."""
        self.assertTrue(
            not has_handlers(
                self.observer, self.scheduler.watchdog_watch
            )
        )
        self.assertTrue(not self.scheduler.is_scheduled)
        self.scheduler.schedule()
        self.assertTrue(
            has_handlers(self.observer, self.scheduler.watchdog_watch)
        )
        self.assertTrue(self.scheduler.is_scheduled)
        self.scheduler.unschedule()
        self.assertTrue(
            not has_handlers(
                self.observer, self.scheduler.watchdog_watch
            )
        )
        self.assertTrue(not self.scheduler.is_scheduled)

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
            watched_path=self.watched_path,
            watching_observer=self.observer,
        )
        other_scheduler.schedule()
        self.scheduler.schedule()
        self.assertTrue(self.scheduler.is_scheduled)
        self.scheduler.unschedule()
        self.assertTrue(not self.scheduler.is_scheduled)
        self.assertTrue(
            has_handlers(self.observer, other_scheduler.watchdog_watch)
        )

    def test_unschedule_manually_unscheduled_handler(self) -> None:
        """
        Unschedule manually unschedule handler should be fine.

        Already satisfied the postcondition of being unscheduled.
        So just say it is succeeded.
        """
        self.scheduler.schedule()
        self.assertTrue(self.scheduler.is_scheduled)
        self.observer.unschedule(self.scheduler.watchdog_watch)
        self.scheduler.unschedule()
        self.assertTrue(not self.scheduler.is_scheduled)

    def test_dispatch_file_creation_events(self) -> None:
        """File creation events passes through."""
        file_path = pathlib.Path('created')
        source_event = watchdog.events.FileCreatedEvent(str(file_path))
        self.scheduler.dispatch(source_event)
        self.assertEqual(self.path_handler.call_args.args[0], file_path)

    def test_dispatch_ignores_directory_events(self) -> None:
        """Directory events are not considered as file events here."""
        file_path = pathlib.Path('directory')
        source_event = watchdog.events.DirCreatedEvent(str(file_path))
        self.scheduler.dispatch(source_event)
        self.path_handler.assert_not_called()

    def test_dispatch_splits_move_events(self) -> None:
        """Move events should be split into two paths."""
        source_path = pathlib.Path('source')
        dest_path = pathlib.Path('dest')
        source_event = watchdog.events.FileMovedEvent(
            str(source_path), str(dest_path)
        )
        self.scheduler.dispatch(source_event)
        self.assertSetEqual(
            set(
                call_args.args[0]
                for call_args in self.path_handler.call_args_list
            ), {source_path, dest_path}
        )

    def test_dispatch_ignores_directory_move_events(self) -> None:
        """Directory events should be ignored even for move events."""
        source_path = pathlib.Path('source')
        dest_path = pathlib.Path('dest')
        source_event = watchdog.events.DirMovedEvent(
            str(source_path), str(dest_path)
        )
        self.scheduler.dispatch(source_event)
        self.path_handler.assert_not_called()

    def test_filter_fails_path(self) -> None:
        """Paths that fails the filter are not passed to the handler."""
        self.path_filter.side_effect = [False, False]
        source_path = pathlib.Path('source')
        dest_path = pathlib.Path('dest')
        source_event = watchdog.events.FileMovedEvent(
            str(source_path), str(dest_path)
        )
        self.scheduler.dispatch(source_event)
        self.assertSetEqual(
            set(
                call_args.args[0]
                for call_args in self.path_filter.call_args_list
            ), {source_path, dest_path}
        )
        self.path_handler.assert_not_called()

    def test_filter_passes_path(self) -> None:
        """Paths that pass the filter goes to the handler."""
        self.path_filter.side_effect = [True, True]
        source_path = pathlib.Path('source')
        dest_path = pathlib.Path('dest')
        source_event = watchdog.events.FileMovedEvent(
            str(source_path), str(dest_path)
        )
        self.scheduler.dispatch(source_event)
        self.assertSetEqual(
            set(
                call_args.args[0]
                for call_args in self.path_filter.call_args_list
            ), {source_path, dest_path}
        )
        self.assertSetEqual(
            set(
                call_args.args[0]
                for call_args in self.path_handler.call_args_list
            ), {source_path, dest_path}
        )


if __name__ == '__main__':
    unittest.main()
