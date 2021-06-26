#!/usr/bin/env python3
"""
------------------------
Test :mod:`phile.signal`
------------------------
"""

# Standard libraries.
import os
import signal
import socket
import types
import unittest

# Internal libraries.
import phile.signal


class TestGetWakeupFd(unittest.TestCase):

    def test_returns_fd(self) -> None:
        file_socket = socket.socket()
        self.addCleanup(file_socket.close)
        file_socket.setblocking(False)
        fileno = file_socket.fileno()
        self.addCleanup(
            signal.set_wakeup_fd, signal.set_wakeup_fd(fileno)
        )
        self.assertEqual(phile.signal.get_wakeup_fd(), fileno)


class TestHandler(unittest.TestCase):

    def test_lambda_can_be_a_handler(self) -> None:
        _handler: phile.signal.Handler = (
            lambda _signal_number, _frame: None
        )

    def test_function_can_be_a_handler(self) -> None:

        def callback(
            _signal_number: signal.Signals, _frame: types.FrameType
        ) -> int:
            return 0

        _handler: phile.signal.Handler = callback


class TestSignalHandlerParameter(unittest.TestCase):

    def test_special_values(self) -> None:
        _default: phile.signal.SignalHandlerParameter = signal.SIG_DFL
        _ignore: phile.signal.SignalHandlerParameter = signal.SIG_IGN

    def test_handler_can_be_an_argument(self) -> None:
        handler: phile.signal.Handler = (
            lambda _signal_number, _frame: None
        )
        _parameter: phile.signal.SignalHandlerParameter = handler


class TestInstallNoopSignalHandler(unittest.TestCase):

    def test_replace_sigint_successfully(self) -> None:
        # For coverage. Unable to test whether a noop is installed.
        self.addCleanup(
            signal.signal, signal.SIGINT,
            signal.getsignal(signal.SIGINT)
        )
        # Install a handler that throws,
        # if the tested function did not install a noop.
        signal.signal(
            signal.SIGINT, lambda _signal_number, _frame: self.
            fail('SIGINT handler not replaced.')
        )
        # Call the function.
        # It should replace the lambda above.
        phile.signal.install_noop_signal_handler(signal.SIGINT)
        # Try running the function.
        # The failing lambda should have been replaced and not run.
        # Cannot really test it is a noop though.
        os.kill(os.getpid(), signal.SIGINT)
