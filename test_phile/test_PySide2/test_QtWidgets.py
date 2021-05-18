#!/usr/bin/env python3
"""
-----------------------------------
Test :mod:`phile.PySide2.QtWidgets`
-----------------------------------
"""

# Standard library.
import unittest

# External dependencies.
import PySide2.QtGui
import PySide2.QtWidgets

# Internal packages.
import phile.PySide2.QtCore
import phile.PySide2.QtWidgets
from .test_QtCore import UsesPySide2


class UsesQApplication(UsesPySide2, unittest.TestCase):

    def setUp(self) -> None:
        """Starts a ``QApplication`` that will be cleaned up."""
        super().setUp()
        self.qapplication = PySide2.QtWidgets.QApplication()


class TestOffscreenSystemTrayIcon(UsesQApplication, unittest.TestCase):
    """
    Tests :class:`~phile.PySide2.QtWidgets.OffscreenSystemTrayIcon`.
    """

    def test_can_default_construct(self) -> None:
        tray_icon = phile.PySide2.QtWidgets.OffscreenSystemTrayIcon()

    def test_init_accepts_new_icon(self) -> None:
        icon = PySide2.QtGui.QIcon()
        tray_icon = phile.PySide2.QtWidgets.OffscreenSystemTrayIcon(icon)

    def test_get_icon(self) -> None:
        pixmap = PySide2.QtGui.QPixmap(1, 1)
        icon = PySide2.QtGui.QIcon(pixmap)
        tray_icon = phile.PySide2.QtWidgets.OffscreenSystemTrayIcon(icon)
        self.assertEqual(tray_icon.icon().cacheKey(), icon.cacheKey())

    def test_set_icon(self) -> None:
        tray_icon = phile.PySide2.QtWidgets.OffscreenSystemTrayIcon()
        icon = PySide2.QtGui.QIcon()
        tray_icon.setIcon(icon)
        self.assertEqual(tray_icon.icon().cacheKey(), icon.cacheKey())
