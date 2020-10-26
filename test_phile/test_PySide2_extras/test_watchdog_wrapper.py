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
import watchdog.events  # type: ignore[import]

# Internal packages.
import phile.PySide2_extras.watchdog_wrapper
import test_phile.pyside2_test_tools

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


class TestSignalEmitter(unittest.TestCase):
    """
    Tests :class:`~phile.PySide2_extras.watchdog_wrapper.SignalEmitter`.
    """

    def setUp(self) -> None:
        """
        Create a PySide2 application before each method test.

        It has to be created to do initialisation
        for GUI widgets to work.
        A new one is created for each test
        to make sure no application state information
        would interfere with each other.
        """
        self.app = test_phile.pyside2_test_tools.QTestApplication()
        self.addCleanup(self.app.tear_down)
        self.event_handler = unittest.mock.Mock()
        self.signal_emitter = (
            phile.PySide2_extras.watchdog_wrapper.SignalEmitter(
                self.app,
                event_handler=self.event_handler,
            )
        )
        self.addCleanup(self.signal_emitter.deleteLater)

    def test_dispatch(self) -> None:
        """Dispatch emits a signal."""
        event_to_forward = watchdog.events.FileCreatedEvent(
            str(pathlib.Path())
        )
        self.signal_emitter(event_to_forward)
        self.app.process_events()
        self.event_handler.assert_called_with(event_to_forward)


if __name__ == '__main__':
    unittest.main()
