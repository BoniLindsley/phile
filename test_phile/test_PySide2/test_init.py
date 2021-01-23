#!/usr/bin/env python3
"""
-------------------------
Test :mod:`phile.PySide2`
-------------------------
"""

# Standard library.
import functools
import tempfile
import threading
import unittest
import unittest.mock

# External dependencies.
import PySide2.QtCore

# Internal packages.
import phile.PySide2
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


class TestProcessDeferredDeleteEvents(UsesPySide2, unittest.TestCase):
    """Tests :class:`~phile.PySide2.process_deferred_delete_events`."""

    def test_deletion_are_triggered(self) -> None:
        application = PySide2.QtCore.QCoreApplication()
        self.addCleanup(application.shutdown)
        callback = unittest.mock.Mock()
        object = PySide2.QtCore.QObject()
        object.destroyed.connect(callback)
        object.deleteLater()
        phile.PySide2.process_deferred_delete_events()
        callback.assert_called_once_with()


class TestProcessEvents(UsesPySide2, unittest.TestCase):
    """Tests :class:`~phile.PySide2.process_events`."""

    def test_timer_events_are_triggered(self) -> None:
        application = PySide2.QtCore.QCoreApplication()
        self.addCleanup(application.shutdown)
        self.addCleanup(phile.PySide2.process_deferred_delete_events)

        class TimedObject(PySide2.QtCore.QObject):

            def __init__(self, *args, **kwargs) -> None:
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
        phile.PySide2.process_events()
        self.assertTrue(object.timer_triggered)


class UsesQCoreApplication(UsesPySide2, unittest.TestCase):

    def setUp(self) -> None:
        """Starts a ``QCoreApplication`` that will be cleaned up."""
        super().setUp()
        application = PySide2.QtCore.QCoreApplication()
        self.addCleanup(application.shutdown)
        self.addCleanup(phile.PySide2.process_deferred_delete_events)
        self.addCleanup(phile.PySide2.process_events)


class TestCallRequest(unittest.TestCase):
    """Tests :class:`~phile.PySide2.CallRequest`."""

    def test_requires_callback_argument(self) -> None:
        self.assertRaises(TypeError, phile.PySide2.CallRequest)

    def test_stores_callback(self) -> None:
        callback = lambda: None
        call_request = phile.PySide2.CallRequest(callback=callback)
        self.assertEqual(call_request.callback, callback)


class TestCaller(UsesQCoreApplication, unittest.TestCase):
    """Tests :class:`~phile.PySide2.Caller`."""

    def test_calls_callback_in_call_requests(self) -> None:
        callback = unittest.mock.Mock()
        caller = phile.PySide2.Caller()
        self.addCleanup(caller.deleteLater)
        caller.event(phile.PySide2.CallRequest(callback=callback))
        callback.assert_called_once_with()

    def test_deletes_self_after_calling_callback(self) -> None:
        caller = phile.PySide2.Caller()
        try:
            callback = unittest.mock.Mock()
            caller.destroyed.connect(callback)
            caller.event(
                phile.PySide2.CallRequest(callback=lambda: None)
            )
            phile.PySide2.process_deferred_delete_events()
            callback.assert_called_once_with()
        except:
            caller.deleteLater()
            raise

    def test_ignores_events_that_are_not_call_requests(self) -> None:
        caller = phile.PySide2.Caller()
        self.addCleanup(caller.deleteLater)
        callback = unittest.mock.Mock()
        caller.destroyed.connect(callback)
        caller.event(PySide2.QtCore.QEvent(PySide2.QtCore.QEvent.User))
        phile.PySide2.process_deferred_delete_events()
        callback.assert_not_called()

    def test_processing_posted_events_sends_requests(self) -> None:
        callback = unittest.mock.Mock()
        caller = phile.PySide2.Caller()
        PySide2.QtCore.QCoreApplication.postEvent(
            caller, phile.PySide2.CallRequest(callback=callback)
        )
        phile.PySide2.process_events()
        phile.PySide2.process_deferred_delete_events()
        callback.assert_called_once_with()


class TestCallSoonThreadsafe(UsesQCoreApplication, unittest.TestCase):
    """Tests :class:`~phile.PySide2.call_soon_threadsafe`."""

    def test_calls_callback_eventually(self) -> None:
        callback = unittest.mock.Mock()
        phile.PySide2.call_soon_threadsafe(callback)
        phile.PySide2.process_events()
        phile.PySide2.process_deferred_delete_events()
        callback.assert_called_once_with()

    def test_passes_positional_arguments_to_callback(self) -> None:
        callback = unittest.mock.Mock()
        phile.PySide2.call_soon_threadsafe(callback, 0)
        phile.PySide2.process_events()
        phile.PySide2.process_deferred_delete_events()
        callback.assert_called_once_with(0)

    def test_calls_from_different_thread_defaults_to_main(self) -> None:
        callback = unittest.mock.Mock()
        worker = threading.Thread(
            target=functools.
            partial(phile.PySide2.call_soon_threadsafe, callback)
        )
        worker.start()
        worker.join()
        phile.PySide2.process_events()
        phile.PySide2.process_deferred_delete_events()
        callback.assert_called_once_with()

    def test_call_into_specified_thread(self) -> None:
        callback = unittest.mock.Mock()
        worker = threading.Thread(
            target=functools.partial(
                phile.PySide2.call_soon_threadsafe,
                callback,
                thread=(
                    PySide2.QtCore.QCoreApplication.instance().thread()
                )
            )
        )
        worker.start()
        worker.join()
        phile.PySide2.process_events()
        phile.PySide2.process_deferred_delete_events()
        callback.assert_called_once_with()

    def test_cleans_up_internal_object_if_error(self) -> None:
        """For coverage. Unable to ensure clean-up is done."""
        self.assertRaises(
            TypeError,
            phile.PySide2.call_soon_threadsafe,
            unittest.mock.Mock(),
            thread=0
        )
