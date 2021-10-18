#!/usr/bin/env python3
"""
-----------------------------------
Test :mod:`phile.PySide2.QtNetwork`
-----------------------------------
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
import PySide2.QtCore

# Internal packages.
import phile.PySide2.QtCore
import phile.PySide2.QtNetwork
import phile.signal
from .test_QtCore import UsesQCoreApplication

platform_can_handle_sigint = sys.platform != "win32"


@unittest.skipUnless(
    platform_can_handle_sigint, "Cannot handle SIGINT on this platform."
)
class TestPosixSignal(UsesQCoreApplication, unittest.TestCase):
    def setUp(self) -> None:
        """
        Create a PySide2 application before each method test.

        It has to be created to do initialisation
        for GUI widgets to work.
        A new one is created for each test
        to make sure no application state information
        would interfere with each other.
        """
        sigint_handler = signal.getsignal(signal.SIGINT)
        self.addCleanup(
            lambda: signal.signal(signal.SIGINT, sigint_handler)
        )
        wakeup_fd = phile.signal.get_wakeup_fd()
        self.addCleanup(lambda: signal.set_wakeup_fd(wakeup_fd))
        super().setUp()
        self.posix_signal = phile.PySide2.QtNetwork.PosixSignal()
        # Allow posix_signal to be deleted in unit tests.
        # They can create an arbitrary QObject to fake a clean-up.
        self.addCleanup(lambda: self.posix_signal.deleteLater())

    def test_remove_signal_fd_when_deleted(self) -> None:
        self.assertNotEqual(phile.signal.get_wakeup_fd(), -1)

        self.posix_signal.deleteLater()
        phile.PySide2.QtCore.process_deferred_delete_events()
        self.assertEqual(phile.signal.get_wakeup_fd(), -1)

        # Give the test `tearDown` something to delete.
        self.posix_signal = PySide2.QtCore.QObject()

    def test_double_initialisation_should_fail(self) -> None:
        self.assertNotEqual(phile.signal.get_wakeup_fd(), -1)
        with self.assertRaises(RuntimeError):
            new_posix_signal = phile.PySide2.QtNetwork.PosixSignal()
        self.assertNotEqual(phile.signal.get_wakeup_fd(), -1)

    def test_handle_sigint_using_pyside2_signal(self) -> None:
        # Figure out whether the signal will be called.
        slot_mock = unittest.mock.Mock()
        self.posix_signal.signal_received.connect(slot_mock)
        # Make sure `posix_signal` receives SIGINT.
        # Normal usage would use `install_noop_signal_handler` here,
        # but we want to use a `signal` to ensure the signal
        # was processed.
        signal_signal_event = threading.Event()
        signal.signal(
            signal.SIGINT,
            lambda signal_number, _: signal_signal_event.set(),
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
        phile.PySide2.QtCore.process_events()
        self.assertTrue(slot_mock.called)


if __name__ == "__main__":
    unittest.main()
