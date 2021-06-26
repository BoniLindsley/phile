#!/usr/bin/env python3
"""
--------------------------------
Test :mod:`phile.PySide2.QtCore`
--------------------------------
"""

# Standard library.
import concurrent.futures
import datetime
import functools
import tempfile
import threading
import typing
import unittest
import unittest.mock

# External dependencies.
import PySide2.QtCore

# Internal packages.
import phile.PySide2.QtCore
import phile.os
import phile.signal


class UsesPySide2(unittest.TestCase):

    def setUp(self) -> None:
        """
        Set up ``PySide2`` to not use user settings.

        Test environments are typically not graphical.
        So the Qt Platform Abstraction used is set to ``offscreen``.

        PySide2 also reads runtime data from ``XDG_RUNTIME_DIR``.
        This is overridden to not use user data.
        """
        super().setUp()
        xdg_runtime_dir = tempfile.TemporaryDirectory()
        self.addCleanup(xdg_runtime_dir.cleanup)
        environ = phile.os.Environ()
        self.addCleanup(environ.restore)
        environ.set(
            XDG_RUNTIME_DIR=xdg_runtime_dir.name,
            QT_QPA_PLATFORM='offscreen',
        )

        def cleanup_qapplication() -> None:
            qapplication = PySide2.QtCore.QCoreApplication.instance()
            if qapplication is None:
                return
            try:
                phile.PySide2.QtCore.process_events()
                phile.PySide2.QtCore.process_deferred_delete_events()
            finally:
                qapplication.shutdown()

        self.addCleanup(cleanup_qapplication)


class TestProcessDeferredDeleteEvents(UsesPySide2, unittest.TestCase):

    def test_deletion_are_triggered(self) -> None:
        application = PySide2.QtCore.QCoreApplication()
        self.addCleanup(application.shutdown)
        callback = unittest.mock.Mock()
        object = PySide2.QtCore.QObject()
        object.destroyed.connect(callback)
        object.deleteLater()
        phile.PySide2.QtCore.process_deferred_delete_events()
        callback.assert_called_once_with()


class TestProcessEvents(UsesPySide2, unittest.TestCase):

    def test_timer_events_are_triggered(self) -> None:
        application = PySide2.QtCore.QCoreApplication()
        self.addCleanup(application.shutdown)
        self.addCleanup(
            phile.PySide2.QtCore.process_deferred_delete_events
        )

        class TimedObject(PySide2.QtCore.QObject):

            def __init__(
                self, *args: typing.Any, **kwargs: typing.Any
            ) -> None:
                super().__init__(*args, **kwargs)
                self.timer_triggered = False
                self.timer_id = self.startTimer(0)

            def timerEvent(
                self, _event: PySide2.QtCore.QTimerEvent
            ) -> None:
                self.timer_triggered = True
                self.killTimer(self.timer_id)

        object = TimedObject()
        self.addCleanup(object.deleteLater)
        phile.PySide2.QtCore.process_events()
        self.assertTrue(object.timer_triggered)


class UsesQCoreApplication(UsesPySide2, unittest.TestCase):

    def setUp(self) -> None:
        """Starts a ``QCoreApplication`` that will be cleaned up."""
        super().setUp()
        self.qcoreapplication = PySide2.QtCore.QCoreApplication()


class TestCallRequest(unittest.TestCase):

    def test_requires_callback_argument(self) -> None:
        self.assertRaises(TypeError, phile.PySide2.QtCore.CallRequest)

    def test_stores_callback(self) -> None:
        callback = lambda: None
        call_request = phile.PySide2.QtCore.CallRequest(
            callback=callback
        )
        self.assertEqual(call_request.callback, callback)


class TestCaller(UsesQCoreApplication, unittest.TestCase):

    def test_calls_callback_in_call_requests(self) -> None:
        callback = unittest.mock.Mock()
        caller = phile.PySide2.QtCore.Caller()
        self.addCleanup(caller.deleteLater)
        caller.event(phile.PySide2.QtCore.CallRequest(callback=callback))
        callback.assert_called_once_with()

    def test_deletes_self_after_calling_callback(self) -> None:
        caller = phile.PySide2.QtCore.Caller()
        try:
            callback = unittest.mock.Mock()
            caller.destroyed.connect(callback)
            caller.event(
                phile.PySide2.QtCore.CallRequest(callback=lambda: None)
            )
            phile.PySide2.QtCore.process_deferred_delete_events()
            callback.assert_called_once_with()
        except:
            caller.deleteLater()
            raise

    def test_ignores_events_that_are_not_call_requests(self) -> None:
        caller = phile.PySide2.QtCore.Caller()
        self.addCleanup(caller.deleteLater)
        callback = unittest.mock.Mock()
        caller.destroyed.connect(callback)
        caller.event(PySide2.QtCore.QEvent(PySide2.QtCore.QEvent.User))
        phile.PySide2.QtCore.process_deferred_delete_events()
        callback.assert_not_called()

    def test_processing_posted_events_sends_requests(self) -> None:
        callback = unittest.mock.Mock()
        caller = phile.PySide2.QtCore.Caller()
        PySide2.QtCore.QCoreApplication.postEvent(
            caller, phile.PySide2.QtCore.CallRequest(callback=callback)
        )
        phile.PySide2.QtCore.process_events()
        phile.PySide2.QtCore.process_deferred_delete_events()
        callback.assert_called_once_with()


class TestCallSoonThreadsafe(UsesQCoreApplication, unittest.TestCase):

    def test_calls_callback_eventually(self) -> None:
        callback = unittest.mock.Mock()
        phile.PySide2.QtCore.call_soon_threadsafe(callback)
        phile.PySide2.QtCore.process_events()
        phile.PySide2.QtCore.process_deferred_delete_events()
        callback.assert_called_once_with()

    def test_passes_positional_arguments_to_callback(self) -> None:
        callback = unittest.mock.Mock()
        phile.PySide2.QtCore.call_soon_threadsafe(callback, 0)
        phile.PySide2.QtCore.process_events()
        phile.PySide2.QtCore.process_deferred_delete_events()
        callback.assert_called_once_with(0)

    def test_calls_from_different_thread_defaults_to_main(self) -> None:
        callback = unittest.mock.Mock()
        worker = threading.Thread(
            target=functools.
            partial(phile.PySide2.QtCore.call_soon_threadsafe, callback)
        )
        worker.start()
        worker.join()
        phile.PySide2.QtCore.process_events()
        phile.PySide2.QtCore.process_deferred_delete_events()
        callback.assert_called_once_with()

    def test_call_into_specified_thread(self) -> None:
        callback = unittest.mock.Mock()
        worker = threading.Thread(
            target=functools.partial(
                phile.PySide2.QtCore.call_soon_threadsafe,
                callback,
                thread=(
                    PySide2.QtCore.QCoreApplication.instance().thread()
                )
            )
        )
        worker.start()
        worker.join()
        phile.PySide2.QtCore.process_events()
        phile.PySide2.QtCore.process_deferred_delete_events()
        callback.assert_called_once_with()

    def test_cleans_up_internal_object_if_error(self) -> None:
        # For coverage. Unable to ensure clean-up is done.
        self.assertRaises(
            TypeError,
            phile.PySide2.QtCore.call_soon_threadsafe,
            unittest.mock.Mock(),
            thread=0
        )


class TestFuture(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.done = False

    def done_callback(
        self, future: phile.PySide2.QtCore.Future[int]
    ) -> None:
        del future
        self.done = True

    def test_static_check_add_done_callback(self) -> None:
        future = phile.PySide2.QtCore.Future[int]()
        future.add_done_callback(self.done_callback)
        future.set_result(0)
        self.assertTrue(self.done)


class UserBaseException(BaseException):
    pass


class TestTask(unittest.TestCase):

    def test_run_sets_result(self) -> None:

        def zero() -> int:
            return 0

        task = phile.PySide2.QtCore.Task[int](callback=zero)
        task.run()
        self.assertEqual(task.result(), zero())

    def test_run_propagates_base_exception(self) -> None:

        def bad() -> int:
            raise UserBaseException()

        task = phile.PySide2.QtCore.Task[int](callback=bad)
        task.run()
        with self.assertRaises(UserBaseException):
            task.result()
        self.assertIsInstance(task.exception(), UserBaseException)

    def test_run_respects_cancellation_before_run_call(self) -> None:

        def zero() -> int:
            return 0

        task = phile.PySide2.QtCore.Task[int](callback=zero)
        task.cancel()
        task.run()
        with self.assertRaises(concurrent.futures.CancelledError):
            task.result()


class TestExecutor(UsesQCoreApplication, unittest.TestCase):

    def test_calls_submitted_callable(self) -> None:
        callback_mock = unittest.mock.Mock()
        with phile.PySide2.QtCore.Executor() as executor:
            executor.submit(callback_mock)
            callback_mock.assert_not_called()
            phile.PySide2.QtCore.process_events()
        callback_mock.assert_called_once_with()

    def test_calls_submitted_callable_with_given_arguments(self) -> None:
        callback_mock = unittest.mock.Mock()
        arg = 0
        with phile.PySide2.QtCore.Executor() as executor:
            executor.submit(callback_mock, arg)
            phile.PySide2.QtCore.process_events()
        callback_mock.assert_called_once_with(arg)

    def test_shutdown_twice_is_okay(self) -> None:
        with phile.PySide2.QtCore.Executor() as executor:
            executor.shutdown()

    def test_shutdown_waits_for_task_to_finish(self) -> None:
        callback_mock = unittest.mock.Mock()
        process_gui_events = threading.Event()

        def run() -> None:
            with phile.PySide2.QtCore.Executor() as executor:
                executor.submit(callback_mock)
                process_gui_events.set()
                executor.shutdown()

        worker_thread = threading.Thread(target=run, daemon=True)
        worker_thread.start()
        process_gui_events.wait()
        phile.PySide2.QtCore.process_events()
        worker_thread.join(
            timeout=datetime.timedelta(seconds=2).total_seconds()
        )
        callback_mock.assert_called_with()

    def test_shutdown_can_cancel_futures(self) -> None:
        callback_mock = unittest.mock.Mock()
        process_gui_events = threading.Event()

        def run() -> None:
            with phile.PySide2.QtCore.Executor() as executor:
                executor.submit(callback_mock)
                executor.shutdown(cancel_futures=True)
                process_gui_events.set()

        worker_thread = threading.Thread(target=run, daemon=True)
        worker_thread.start()
        process_gui_events.wait()
        phile.PySide2.QtCore.process_events()
        worker_thread.join(
            timeout=datetime.timedelta(seconds=2).total_seconds()
        )
        callback_mock.assert_not_called()

    def test_shutdown_does_not_have_to_wait(self) -> None:
        callback_mock = unittest.mock.Mock()
        process_gui_events = threading.Event()

        def run() -> None:
            with phile.PySide2.QtCore.Executor() as executor:
                executor.submit(callback_mock)
                executor.shutdown(wait=False)
                process_gui_events.set()

        worker_thread = threading.Thread(target=run, daemon=True)
        worker_thread.start()
        process_gui_events.wait()
        phile.PySide2.QtCore.process_events()
        worker_thread.join(
            timeout=datetime.timedelta(seconds=2).total_seconds()
        )
        callback_mock.assert_called_with()

    def test_submission_fails_after_shutdown(self) -> None:
        with phile.PySide2.QtCore.Executor() as executor:
            pass
        with self.assertRaises(RuntimeError):
            executor.submit(lambda: None)
