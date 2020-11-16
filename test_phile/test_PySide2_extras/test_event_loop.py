#!/usr/bin/env python3
"""
-------------------------------------------
Test :mod:`phile.PySide2_extras.event_loop`
-------------------------------------------
"""

# Standard library.
import unittest
import unittest.mock

# Internal packages.
import phile.PySide2_extras.event_loop
import test_phile.pyside2_test_tools


class TestCallSoon(unittest.TestCase):
    """
    Tests :class:`~phile.PySide2_extras.event_loop.CallSoon`.
    """

    def setUp(self) -> None:
        """
        Create a PySide2 application
        and a :class:`~phile.PySide2_extras.event_loop.CallSoon`
        for testing.
        """
        self.app = test_phile.pyside2_test_tools.QTestApplication()
        self.addCleanup(self.app.tear_down)
        self.event_handler = unittest.mock.Mock()
        self.call_soon = (
            phile.PySide2_extras.event_loop.CallSoon(
                self.app,
                call_target=self.event_handler,
            )
        )
        self.addCleanup(self.call_soon.deleteLater)

    def test_call(self) -> None:
        """
        Calls the given ``call_target`` in the Qt event loop
        whenever :class:`~phile.PySide2_extras.event_loop.CallSoon`
        is called.

        And only in the event loop, not outside the loop.
        """
        argument = 0
        self.call_soon(argument)
        self.event_handler.assert_not_called()
        self.app.process_events()
        self.event_handler.assert_called_with(0)


if __name__ == '__main__':
    unittest.main()
