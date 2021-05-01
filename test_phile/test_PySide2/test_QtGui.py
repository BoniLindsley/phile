#!/usr/bin/env python3
"""
-------------------------------
Test :mod:`phile.PySide2.QtGui`
-------------------------------
"""

# Standard library.
import unittest

# External dependencies.
import PySide2.QtGui

# Internal packages.
import phile.PySide2.QtGui
from .test_QtCore import UsesPySide2


class UsesQGuiApplication(UsesPySide2, unittest.TestCase):

    def setUp(self) -> None:
        """Starts a ``QApplication`` that will be cleaned up."""
        super().setUp()
        application = PySide2.QtGui.QGuiApplication()
        self.addCleanup(application.shutdown)
        self.addCleanup(
            phile.PySide2.QtCore.process_deferred_delete_events,
        )
        self.addCleanup(phile.PySide2.QtCore.process_events)


class TestQIconFromSpecifiedTheme(
    UsesQGuiApplication, unittest.TestCase
):
    """
    Tests :class:`~phile.PySide2.QtGui.q_icon_from_specified_theme`.
    """

    def test_can_default_construct(self) -> None:
        icon = phile.PySide2.QtGui.q_icon_from_specified_theme('a', 'b')


class TestQIconFromTheme(UsesQGuiApplication, unittest.TestCase):
    """
    Tests :class:`~phile.PySide2.QtGui.q_icon_from_theme`.
    """

    def test_can_default_construct(self) -> None:
        icon = phile.PySide2.QtGui.q_icon_from_theme('a')
