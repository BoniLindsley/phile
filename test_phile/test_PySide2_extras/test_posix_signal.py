#!/usr/bin/env python3
"""
-----------------
Test POSIX Signal
-----------------
"""

# Standard libraries.
import datetime
import os
import signal
import sys
import threading
import unittest
import unittest.mock

# External dependencies.
from PySide2.QtCore import QObject

# Internal libraries.
from phile.PySide2_extras.posix_signal import (
    install_noop_signal_handler, PosixSignal
)
from test_phile.pyside2_test_tools import QTestApplication

platform_can_handle_sigint = (sys.platform != "win32")


def get_wakeup_fd() -> int:
    """
    Returns the file descriptor stored by :func:`~signal.set_wakeup_fd`.

    Currently, the only way to determine the fd is
    is to use :func:`~signal.set_wakeup_fd` using a dummy value,
    because it returns the previous fd,
    and then once more to restore it.
    This wraps the two calls for convenience.
    """
    wakeup_fd = signal.set_wakeup_fd(-1)
    signal.set_wakeup_fd(wakeup_fd)
    return wakeup_fd


class TestInstallNoopSignalHandler(unittest.TestCase):
    """
    Unit test for
    :class:`~phile.PySide2_extras.posix_signal.install_noop_signal_handler`.
    """

    def __init__(self, *args, **kwargs):
        """"""
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """Remember the current signal handler to be restored later."""
        self.sigint_handler = signal.getsignal(signal.SIGINT)

    def tearDown(self) -> None:
        """Restore the previous signal handler."""
        signal.signal(signal.SIGINT, self.sigint_handler)

    def test_call(self) -> None:
        """Replace SIGINT handler."""
        # Install a handler that throws,
        # if the tested function did not install a noop.
        signal.signal(
            signal.SIGINT, lambda signal_number, _: self.
            fail('SIGINT handler not replaced.')
        )
        # Call the function.
        # It should replace the lambda above.
        install_noop_signal_handler(signal.SIGINT)
        # Try running the function.
        # The failing lambda should have been replaced and not run.
        os.kill(os.getpid(), signal.SIGINT)


@unittest.skipUnless(
    platform_can_handle_sigint, 'Cannot handle SIGINT on this platform.'
)
class TestPosixSignal(unittest.TestCase):
    """
    Unit test for
    :class:`~phile.PySide2_extras.posix_signal.PosixSignal`.
    """

    def __init__(self, *args, **kwargs):
        """"""
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """
        Create a PySide2 application before each method test.

        It has to be created to do initialisation
        for GUI widgets to work.
        A new one is created for each test
        to make sure no application state information
        would interfere with each other.
        """
        self.sigint_handler = signal.getsignal(signal.SIGINT)
        self.wakeup_fd = get_wakeup_fd()
        self.app = QTestApplication()
        self.posix_signal = PosixSignal()

    def tearDown(self) -> None:
        """
        Shutdown PySide2 application after each method test.

        PySide2 Applications act as singletons.
        Any previous instances must be shutdown
        before a new one can be created.
        """
        self.posix_signal.deleteLater()
        self.app.tear_down()
        signal.set_wakeup_fd(self.wakeup_fd)
        signal.signal(signal.SIGINT, self.sigint_handler)

    def test_initialisation_and_clean_up(self) -> None:
        """Remove signal fd when deleted."""
        self.assertNotEqual(get_wakeup_fd(), -1)

        self.posix_signal.deleteLater()
        self.app.process_deferred_delete_events()
        self.assertEqual(get_wakeup_fd(), -1)

        # Give the test `tearDown` something to delete.
        self.posix_signal = QObject()

    def test_double_initialisation(self) -> None:
        """Initialising twice should fail."""
        self.assertNotEqual(get_wakeup_fd(), -1)
        with self.assertRaises(RuntimeError):
            new_posix_signal = PosixSignal()
        self.assertNotEqual(get_wakeup_fd(), -1)

    def test_handle_sigint_using_pyside2_signal(self):
        """Handle POSIX signals using PySide2 signals."""

        # Figure out whether the signal will be called.
        slot_mock = unittest.mock.Mock()
        self.posix_signal.signal_received.connect(
            slot_mock
        )  # type: ignore
        # Make sure `posix_signal` receives SIGINT.
        # Normal usage would use `install_noop_signal_handler` here,
        # but we want to use a `signal` to ensure the signal
        # was processed.
        signal_signal_event = threading.Event()
        signal.signal(
            signal.SIGINT,
            lambda signal_number, _: signal_signal_event.set()
        )
        # Send the signal.
        os.kill(os.getpid(), signal.SIGINT)
        # The signal.signal() handler should have been called.
        wait_time = datetime.timedelta(seconds=2)
        self.assertTrue(
            signal_signal_event.wait(wait_time.total_seconds())
        )
        # If the signal.signal handler has already been called,
        # then the CPython signal handler had already wrote
        # to the signal fd.
        self.app.process_events()
        self.assertTrue(slot_mock.called)


if __name__ == '__main__':
    unittest.main()
