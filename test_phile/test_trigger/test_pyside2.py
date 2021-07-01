#!/usr/bin/env python3

# Standard library.
import unittest

# External dependencies.
import PySide2.QtWidgets

# Internal packages.
import phile.PySide2.QtCore
import phile.trigger.pyside2
from test_phile.test_PySide2.test_QtWidgets import UsesQApplication


class TestTriggerControlled(UsesQApplication, unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.trigger_registry = phile.trigger.Registry()
        self.pyside2_executor = phile.PySide2.QtCore.Executor()

        class TriggerControlledWidget(
            phile.trigger.pyside2.TriggerControlled,
            PySide2.QtWidgets.QWidget,
        ):
            pass

        self.trigger_controlled = TriggerControlledWidget(
            pyside2_executor=self.pyside2_executor,
            trigger_prefix='ptp',
            trigger_registry=self.trigger_registry,
        )
        self.addCleanup(self.trigger_controlled.deleteLater)

    def test_init_binds_triggers(self) -> None:
        registry = self.trigger_registry
        self.assertTrue(registry.is_shown('ptp.show'))
        self.assertTrue(registry.is_bound('ptp.hide'))

    def test_close_unbinds_triggers(self) -> None:
        registry = self.trigger_registry
        self.trigger_controlled.close()
        self.assertFalse(registry.is_bound('ptp.show'))
        self.assertFalse(registry.is_bound('ptp.hide'))

    def test_show_hide_toggles_triggers(self) -> None:
        trigger_controlled = self.trigger_controlled
        registry = self.trigger_registry
        self.assertTrue(trigger_controlled.isHidden())
        self.assertTrue(registry.is_shown('ptp.show'))
        self.assertFalse(registry.is_shown('ptp.hide'))
        trigger_controlled.show()
        self.assertFalse(registry.is_shown('ptp.show'))
        self.assertTrue(registry.is_shown('ptp.hide'))
        trigger_controlled.hide()
        self.assertTrue(registry.is_shown('ptp.show'))
        self.assertFalse(registry.is_shown('ptp.hide'))

    def test_show_hide_ignores_if_triggers_unbound(self) -> None:
        # For coverage.
        trigger_controlled = self.trigger_controlled
        trigger_controlled.trigger_producer.unbind()
        trigger_controlled.show()
        trigger_controlled.hide()
        registry = self.trigger_registry
        self.assertFalse(registry.is_shown('ptp.show'))
        self.assertFalse(registry.is_shown('ptp.hide'))
