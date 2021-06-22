#!/usr/bin/env python3
"""
--------------------------
Test :mod:`phile.watchdog`
--------------------------
"""

# Standard library.
import dataclasses
import pathlib
import unittest
import unittest.mock

# External dependencies.
import watchdog.events
import watchdog.observers

# Internal packages.
import phile.watchdog
import phile.watchdog.observers

IntCallback = (phile.watchdog.SingleParameterCallback[int, None])


class TestSingleParameterCallback(unittest.TestCase):
    """Tests :data:`~phile.watchdog.SingleParameterCallback`."""

    def do_callback_test(self, callback: IntCallback) -> None:
        """
        Calls ``callback`` directly and as a member.

        Call signature also checks the given ``callback`` in ``mypy``.
        """

        callback(0)

        @dataclasses.dataclass
        class Parent:
            callback: IntCallback

        parent = Parent(callback=callback)
        parent.callback(0)

    def test_class_method(self) -> None:
        """Methods of with proper parameter satisfies the protocol."""

        class IntObject:

            @classmethod
            def int_method(cls, _: int) -> None:
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
    """Tests :data:`~phile.watchdog.EventHandler`."""

    def test_function(self) -> None:
        """
        A function can be a :data:`~phile.watchdog.EventHandler`.
        """

        def event_handle_function(
            _event: watchdog.events.FileSystemEvent
        ) -> None:
            pass

        _: phile.watchdog.EventHandler = event_handle_function


class TestPathFilter(unittest.TestCase):
    """Tests :data:`~phile.watchdog.PathFilter`."""

    def test_function(self) -> None:
        """
        A function can be a :data:`~phile.watchdog.PathFilter`.
        """

        def path_handle_function(_path: pathlib.Path) -> bool:
            return True

        path_filter: phile.watchdog.PathFilter = (path_handle_function)
        self.assertTrue(path_filter(pathlib.Path()))


class TestPathHandler(unittest.TestCase):
    """Tests :data:`~phile.watchdog.PathHandler`."""

    def test_function(self) -> None:
        """
        A function can be a :data:`~phile.watchdog.PathHandler`.
        """

        def path_handle_function(_path: pathlib.Path) -> None:
            pass

        handler: phile.watchdog.PathHandler = (path_handle_function)
        handler(pathlib.Path())


class TestScheduler(unittest.TestCase):
    """Unit test for :class:`~phile.watchdog.Scheduler`."""

    def setUp(self) -> None:
        """Create a handler to forward to."""
        self.observer = observer = watchdog.observers.Observer()
        self.addCleanup(self.observer.stop)
        self.watched_path = watched_path = pathlib.Path()
        self.path_filter = path_filter = unittest.mock.Mock()
        self.path_handler = path_handler = unittest.mock.Mock()
        self.scheduler = phile.watchdog.Scheduler(
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
        other_scheduler = phile.watchdog.Scheduler(
            watched_path=self.watched_path,
            watching_observer=self.observer,
        )
        file_path = pathlib.Path('created')
        source_event = watchdog.events.FileCreatedEvent(str(file_path))
        other_scheduler.dispatch(source_event)

    def test_is_scheduled(self) -> None:
        """Dispatching calls the given handler."""
        self.assertTrue(not self.scheduler.is_scheduled)
        self.scheduler.schedule()
        self.assertTrue(self.scheduler.is_scheduled)
        self.scheduler.unschedule()
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
        other_scheduler = phile.watchdog.Scheduler(
            watched_path=self.watched_path,
            watching_observer=self.observer,
        )
        other_scheduler.schedule()
        self.scheduler.schedule()
        self.assertTrue(self.scheduler.is_scheduled)
        self.scheduler.unschedule()
        self.assertTrue(not self.scheduler.is_scheduled)
        self.assertIsNotNone(other_scheduler.watchdog_watch)
        assert other_scheduler.watchdog_watch is not None
        self.assertTrue(
            phile.watchdog.observers.has_handlers(
                self.observer, other_scheduler.watchdog_watch
            )
        )

    def test_unschedule_manually_unscheduled_handler(self) -> None:
        """
        Unschedule manually unschedule handler should be fine.

        Already satisfied the postcondition of being unscheduled.
        So just say it is succeeded.
        """
        self.scheduler.schedule()
        self.assertTrue(self.scheduler.is_scheduled)
        self.assertIsNotNone(self.scheduler.watchdog_watch)
        assert self.scheduler.watchdog_watch is not None
        self.observer.unschedule(self.scheduler.watchdog_watch)
        self.scheduler.unschedule()
        self.assertTrue(not self.scheduler.is_scheduled)

    def test_schedule_in_context_manager(self) -> None:
        scheduler = self.scheduler
        with scheduler:
            self.assertTrue(scheduler.is_scheduled)
        self.assertTrue(not scheduler.is_scheduled)

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
