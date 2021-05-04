#!/usr/bin/env python3
"""
--------------------------------
Test :mod:`phile.hotkey.pyside2`
--------------------------------
"""

# Standard library.
import concurrent.futures
import datetime
import threading
import typing
import unittest
import unittest.mock

# External dependencies.
import PySide2.QtCore
import PySide2.QtGui

# Internal packages.
import phile.hotkey.pyside2
import phile.PySide2.QtCore
import phile.os
import phile.signal
from test_phile.test_init import UsesCapabilities, UsesConfiguration
from test_phile.test_PySide2.test_QtCore import (
    UsesExecutor, UsesQCoreApplication
)
from test_phile.test_PySide2.test_QtWidgets import UsesQApplication
from test_phile.test_trigger.test_init import UsesRegistry


class TestKeyValueFromString(unittest.TestCase):
    """Tests :class:`~phile.hotkey.pyside2.key_value_from_string`."""

    def test_alphabet_conversion(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_value_from_string('A'),
            PySide2.QtGui.Qt.Key_A,
        )

    def test_angle_bracket_removal(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_value_from_string('<Alt>'),
            PySide2.QtGui.Qt.Key_Alt,
        )

    def test_alternative_key_names(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_value_from_string('<Ctrl>'),
            PySide2.QtGui.Qt.Key_Control,
        )
        self.assertEqual(
            phile.hotkey.pyside2.key_value_from_string('<Esc>'),
            PySide2.QtGui.Qt.Key_Escape,
        )


class TestKeyCombinationFromString(unittest.TestCase):
    """
    Tests :class:`~phile.hotkey.pyside2.key_combination_from_string`.
    """

    def test_single_key(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_combination_from_string('A'),
            (PySide2.QtGui.Qt.Key_A, ),
        )

    def test_key_names_separated_by_plus(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.
            key_combination_from_string('<Ctrl>+<Alt>'), (
                PySide2.QtGui.Qt.Key_Control,
                PySide2.QtGui.Qt.Key_Alt,
            )
        )

    def test_sorts_by_value(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.
            key_combination_from_string('<Ctrl>+<Alt>+<Shift>'), (
                PySide2.QtGui.Qt.Key_Shift,
                PySide2.QtGui.Qt.Key_Control,
                PySide2.QtGui.Qt.Key_Alt,
            )
        )


class TestKeySequenceFromString(unittest.TestCase):
    """Tests :class:`~phile.hotkey.pyside2.key_sequence_from_string`."""

    def test_single_combination(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.
            key_sequence_from_string('<Ctrl>+<Alt>+<Shift>'), ((
                PySide2.QtGui.Qt.Key_Shift,
                PySide2.QtGui.Qt.Key_Control,
                PySide2.QtGui.Qt.Key_Alt,
            ), )
        )

    def test_combinations_separated_by_semi_colon(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.
            key_sequence_from_string('<Ctrl>+<Alt>+<Shift>; <Meta>'), ((
                PySide2.QtGui.Qt.Key_Shift,
                PySide2.QtGui.Qt.Key_Control,
                PySide2.QtGui.Qt.Key_Alt,
            ), (PySide2.QtGui.Qt.Key_Meta, ))
        )


class TestOrderKeySequence(unittest.TestCase):
    """Tests :class:`~phile.hotkey.pyside2.order_key_sequence`."""

    def test_default_order(self) -> None:
        self.assertEqual(
            tuple(
                phile.hotkey.pyside2.order_key_sequence(
                    phile.hotkey.pyside2.key_combination_from_string(
                        '<Alt>+<Ctrl>+<Meta>+<Shift>'
                    )
                )
            ), (
                PySide2.QtGui.Qt.Key_Meta,
                PySide2.QtGui.Qt.Key_Control,
                PySide2.QtGui.Qt.Key_Alt,
                PySide2.QtGui.Qt.Key_Shift,
            )
        )


class TestKeyValueToString(unittest.TestCase):
    """Tests :class:`~phile.hotkey.pyside2.key_value_to_string`."""

    def test_alphabet_conversion(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_value_to_string(
                PySide2.QtGui.Qt.Key_A
            ),
            'A',
        )

    def test_angle_bracket_removal(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_value_to_string(
                PySide2.QtGui.Qt.Key_Alt
            ),
            'Alt',
        )

    def test_alternative_key_names(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_value_to_string(
                PySide2.QtGui.Qt.Key_Control
            ),
            'Ctrl',
        )
        self.assertEqual(
            phile.hotkey.pyside2.key_value_to_string(
                PySide2.QtGui.Qt.Key_Escape
            ),
            'Esc',
        )

    def test_one_way_round_trip_conversion(self) -> None:
        key = PySide2.QtGui.Qt.Key_Control

        self.assertEqual(
            phile.hotkey.pyside2.key_value_from_string(
                phile.hotkey.pyside2.key_value_to_string(key)
            ), key
        )


class TestKeyCombinationToString(unittest.TestCase):
    """Tests :class:`~phile.hotkey.pyside2.key_combination_to_string`."""

    def test_single_key(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_combination_to_string(
                (PySide2.QtGui.Qt.Key_A, )
            ),
            'A',
        )

    def test_key_names_separated_by_plus(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_combination_to_string((
                PySide2.QtGui.Qt.Key_Control,
                PySide2.QtGui.Qt.Key_Alt,
            )),
            'Ctrl+Alt',
        )

    def test_sorts_by_value(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_combination_to_string((
                PySide2.QtGui.Qt.Key_Shift,
                PySide2.QtGui.Qt.Key_Control,
                PySide2.QtGui.Qt.Key_Alt,
            )),
            'Ctrl+Alt+Shift',
        )


class TestKeySequenceToString(unittest.TestCase):
    """Tests :class:`~phile.hotkey.pyside2.key_sequence_to_string`."""

    def test_single_combination(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_sequence_to_string(((
                PySide2.QtGui.Qt.Key_Shift,
                PySide2.QtGui.Qt.Key_Control,
                PySide2.QtGui.Qt.Key_Alt,
            ), ), ),
            'Ctrl+Alt+Shift',
        )

    def test_combinations_separated_by_semi_colon(self) -> None:
        self.assertEqual(
            phile.hotkey.pyside2.key_sequence_to_string((
                (
                    PySide2.QtGui.Qt.Key_Shift,
                    PySide2.QtGui.Qt.Key_Control,
                    PySide2.QtGui.Qt.Key_Alt,
                ),
                (PySide2.QtGui.Qt.Key_Meta, ),
            )),
            'Ctrl+Alt+Shift; Meta',
        )


class TestPressedKeys(UsesQApplication, unittest.TestCase):
    """Tests :class:`~phile.hotkey.pyside2.PressedKeys`."""

    def setUp(self) -> None:
        super().setUp()

        class KeysWidget(
            phile.hotkey.pyside2.PressedKeys, PySide2.QtWidgets.QWidget
        ):

            def __init__(
                self, *args: typing.Any, **kwargs: typing.Any
            ) -> None:
                super().__init__(*args, **kwargs)
                self.is_on_pressed_keys_changed_called = False

            def on_pressed_keys_changed(
                self, event: PySide2.QtGui.QKeyEvent
            ) -> None:
                super().on_pressed_keys_changed(event)
                self.is_on_pressed_keys_changed_called = True

        self.keys_widget = KeysWidget()
        self.addCleanup(self.keys_widget.deleteLater)

    def test_raises_if_not_qobject(self) -> None:
        with self.assertRaises(AttributeError):
            phile.hotkey.pyside2.PressedKeys()

    def test_raises_if_not_qwidget(self) -> None:

        class NotQWidget(
            phile.hotkey.pyside2.PressedKeys, PySide2.QtCore.QObject
        ):
            pass

        with self.assertRaises(AssertionError):
            NotQWidget()

    def do_process_key_event(
        self, event: PySide2.QtGui.QKeyEvent
    ) -> None:
        PySide2.QtWidgets.QApplication.instance().postEvent(
            self.keys_widget, event
        )
        phile.PySide2.QtCore.process_events()

    def do_press_key(self, key: PySide2.QtCore.Qt.Key) -> None:
        event = PySide2.QtGui.QKeyEvent(
            PySide2.QtCore.QEvent.Type.KeyPress,
            int(key),  # type: ignore[call-overload]
            PySide2.QtCore.Qt.KeyboardModifiers(),
            0,
            0,
            0
        )
        self.do_process_key_event(event)

    def do_release_key(self, key: PySide2.QtCore.Qt.Key) -> None:
        event = PySide2.QtGui.QKeyEvent(
            PySide2.QtCore.QEvent.Type.KeyRelease,
            int(key),  # type: ignore[call-overload]
            PySide2.QtCore.Qt.KeyboardModifiers(),
            0,
            0,
            0,
        )
        self.do_process_key_event(event)

    def test_has_expected_attributes(self) -> None:
        _pressed_keys: set[int] = self.keys_widget.pressed_keys

    def test_remembers_pressed_and_released_keys(self) -> None:
        key = PySide2.QtCore.Qt.Key.Key_A
        self.do_press_key(key)
        self.assertEqual(self.keys_widget.pressed_keys, {key})
        key_2 = PySide2.QtCore.Qt.Key.Key_B
        self.do_press_key(key_2)
        self.assertEqual(self.keys_widget.pressed_keys, {key, key_2})
        self.do_release_key(key)
        self.assertEqual(self.keys_widget.pressed_keys, {key_2})

    def test_calls_on_pressed_keys_changed(self) -> None:
        key = PySide2.QtCore.Qt.Key.Key_A
        self.do_press_key(key)
        self.assertTrue(
            self.keys_widget.is_on_pressed_keys_changed_called
        )

    def test_release_ignores_unpressed_keys(self) -> None:
        key = PySide2.QtCore.Qt.Key.Key_A
        self.do_press_key(key)
        self.assertEqual(self.keys_widget.pressed_keys, {key})
        key_2 = PySide2.QtCore.Qt.Key.Key_B
        self.do_release_key(key_2)
        self.assertEqual(self.keys_widget.pressed_keys, {key})

    def test_ignores_auto_repeat(self) -> None:
        key = PySide2.QtCore.Qt.Key.Key_A
        event = PySide2.QtGui.QKeyEvent(
            PySide2.QtCore.QEvent.Type.KeyPress,
            int(key),  # type: ignore[call-overload]
            PySide2.QtCore.Qt.KeyboardModifiers(),
            0,
            0,
            0,
            '',
            True,
            1,
        )
        self.keys_widget.keyPressEvent(event)
        self.assertEqual(self.keys_widget.pressed_keys, set())
        self.do_press_key(key)
        self.assertEqual(self.keys_widget.pressed_keys, {key})
        event = PySide2.QtGui.QKeyEvent(
            PySide2.QtCore.QEvent.Type.KeyRelease,
            int(key),  # type: ignore[call-overload]
            PySide2.QtCore.Qt.KeyboardModifiers(),
            0,
            0,
            0,
            '',
            True,
            1,
        )
        self.keys_widget.keyReleaseEvent(event)
        self.assertEqual(self.keys_widget.pressed_keys, {key})

    def test_ignores_unusable_keys(self) -> None:
        key = PySide2.QtCore.Qt.Key.Key_unknown
        self.do_press_key(key)
        self.assertEqual(self.keys_widget.pressed_keys, set())
        key = PySide2.QtCore.Qt.Key()
        self.do_press_key(key)
        self.assertEqual(self.keys_widget.pressed_keys, set())

        useful_key = PySide2.QtCore.Qt.Key.Key_A
        self.do_press_key(useful_key)
        self.assertEqual(self.keys_widget.pressed_keys, {useful_key})

        key = PySide2.QtCore.Qt.Key.Key_unknown
        self.do_release_key(key)
        self.assertEqual(self.keys_widget.pressed_keys, {useful_key})
        key = PySide2.QtCore.Qt.Key()
        self.do_release_key(key)
        self.assertEqual(self.keys_widget.pressed_keys, {useful_key})


class TestPressedKeySequence(UsesQApplication, unittest.TestCase):
    """Tests :class:`~phile.hotkey.pyside2.PressedKeySequence`."""

    def setUp(self) -> None:
        super().setUp()

        class KeySequenceWidget(
            phile.hotkey.pyside2.PressedKeySequence,
            PySide2.QtWidgets.QWidget,
        ):

            def __init__(
                self, *args: typing.Any, **kwargs: typing.Any
            ) -> None:
                super().__init__(*args, **kwargs)
                self.bound_values: list[typing.Any] = []

            def on_pressed_sequence_changed(
                self, bound_value: typing.Any
            ) -> None:
                super().on_pressed_sequence_changed(bound_value)
                self.bound_values.append(bound_value)

        self.key_sequence_widget = KeySequenceWidget()
        self.addCleanup(self.key_sequence_widget.deleteLater)
        self.key_a = int(  # type: ignore[call-overload]
                PySide2.QtCore.Qt.Key.Key_A
        )
        self.key_b = int(  # type: ignore[call-overload]
                PySide2.QtCore.Qt.Key.Key_B
        )

    def do_process_key_event(
        self, event: PySide2.QtGui.QKeyEvent
    ) -> None:
        PySide2.QtWidgets.QApplication.instance().postEvent(
            self.key_sequence_widget, event
        )
        phile.PySide2.QtCore.process_events()

    def do_press_key(self, key: PySide2.QtCore.Qt.Key) -> None:
        event = PySide2.QtGui.QKeyEvent(
            PySide2.QtCore.QEvent.Type.KeyPress,
            int(key),  # type: ignore[call-overload]
            PySide2.QtCore.Qt.KeyboardModifiers(),
            0,
            0,
            0
        )
        self.do_process_key_event(event)

    def do_release_key(self, key: PySide2.QtCore.Qt.Key) -> None:
        event = PySide2.QtGui.QKeyEvent(
            PySide2.QtCore.QEvent.Type.KeyRelease,
            int(key),  # type: ignore[call-overload]
            PySide2.QtCore.Qt.KeyboardModifiers(),
            0,
            0,
            0,
        )
        self.do_process_key_event(event)

    def do_key(self, key: PySide2.QtCore.Qt.Key) -> None:
        self.do_press_key(key)
        self.do_release_key(key)

    def test_has_expected_attributes(self) -> None:
        # TODO[mypy issue 9564]: Use tuple directly.
        # Waiting for pull request to be merged to release.
        KeyCombination = typing.Tuple[int, ...]
        KeySequence = list[KeyCombination]
        KeyBindings = dict[KeyCombination, typing.Any]
        widget = self.key_sequence_widget
        _pressed_sequence: KeySequence = widget.pressed_sequence
        _key_bindings: KeyBindings = widget.key_bindings
        _active_binding: KeyBindings = widget.active_binding

    def test_add_key_bindings(self) -> None:
        self.key_sequence_widget.add_key_bindings({
            'A; B': 'target_trigger'
        })
        self.assertEqual(
            self.key_sequence_widget.key_bindings, {
                (self.key_a, ): {(self.key_b, ): 'target_trigger'},
            }
        )

    def test_add_empty_key_bindings(self) -> None:
        self.key_sequence_widget.add_key_bindings({})
        self.assertEqual(self.key_sequence_widget.key_bindings, {})

    def test_pressing_sequence_records_pressed_sequence(self) -> None:
        self.test_add_key_bindings()
        self.do_key(self.key_a)
        self.assertEqual(
            self.key_sequence_widget.pressed_sequence, [(self.key_a, )]
        )
        self.do_key(self.key_b)
        self.assertEqual(
            self.key_sequence_widget.pressed_sequence, [
                (self.key_a, ),
                (self.key_b, ),
            ]
        )

    def test_pressing_sequence_changes_active_binding(self) -> None:
        self.test_add_key_bindings()
        self.do_key(self.key_a)
        self.assertEqual(
            self.key_sequence_widget.active_binding,
            {(self.key_b, ): 'target_trigger'}
        )
        self.do_key(self.key_b)
        self.assertEqual(self.key_sequence_widget.active_binding, {})

    def test_unknown_sequence_resets_active_binding(self) -> None:
        self.test_add_key_bindings()
        # Use the binding.
        self.do_key(self.key_a)
        self.assertEqual(
            self.key_sequence_widget.active_binding,
            {(self.key_b, ): 'target_trigger'}
        )
        # Use a wrong key. Only `key_b` is bound at this point.
        self.do_key(self.key_a)
        self.assertEqual(self.key_sequence_widget.active_binding, {})
        # Try to use the original binding again.
        self.do_key(self.key_a)
        self.assertEqual(
            self.key_sequence_widget.active_binding,
            {(self.key_b, ): 'target_trigger'}
        )

    def test_unknown_modifier_sequence_is_ignored(self) -> None:
        # Cannot really test that it is ignored.
        # Test for a condition that should be satisfied if ignored.
        # Test is done mostly for coverage.
        self.test_add_key_bindings()
        self.do_key(PySide2.QtCore.Qt.Key.Key_Control)
        self.assertEqual(
            self.key_sequence_widget.active_binding,
            self.key_sequence_widget.key_bindings
        )

    def test_calls_on_pressed_keys_changed(self) -> None:
        self.test_add_key_bindings()
        self.do_key(self.key_a)
        self.assertEqual(
            self.key_sequence_widget.bound_values,
            [{(self.key_b, ): 'target_trigger'}]
        )
        self.key_sequence_widget.bound_values.clear()
        self.do_key(self.key_b)
        self.assertEqual(
            self.key_sequence_widget.bound_values, ['target_trigger']
        )

    def test_reset_clears_pressed_sequence(self) -> None:
        self.test_add_key_bindings()
        self.do_key(self.key_a)
        self.assertTrue(self.key_sequence_widget.pressed_sequence)
        self.key_sequence_widget.reset_pressed_sequence()
        self.assertFalse(self.key_sequence_widget.pressed_sequence)

    def test_reset_calls_on_changed_callback(self) -> None:
        self.test_add_key_bindings()
        self.do_key(self.key_a)
        self.key_sequence_widget.bound_values.clear()
        self.key_sequence_widget.reset_pressed_sequence()
        self.assertEqual(self.key_sequence_widget.bound_values, [None])


class TestHotkeyInput(
    UsesQApplication, UsesRegistry, UsesExecutor, UsesConfiguration,
    UsesCapabilities, unittest.TestCase
):
    """Tests :class:`~phile.hotkey.pyside2.HotkeyInput`."""

    def setUp(self) -> None:
        super().setUp()
        self.alphabet_event = threading.Event()
        self.trigger_registry.bind('alphabet', self.alphabet_event.set)
        self.addCleanup(self.trigger_registry.unbind, 'alphabet')
        self.trigger_registry.show('alphabet')
        self.input = phile.hotkey.pyside2.HotkeyInput(
            capabilities=self.capabilities
        )
        self.addCleanup(self.input.deleteLater)
        self.input.add_key_bindings({'A; B; C': 'alphabet'})

    def do_process_key_event(
        self, event: PySide2.QtGui.QKeyEvent
    ) -> None:
        PySide2.QtWidgets.QApplication.instance().postEvent(
            self.input, event
        )
        phile.PySide2.QtCore.process_events()

    def do_press_key(self, key: PySide2.QtCore.Qt.Key) -> None:
        event = PySide2.QtGui.QKeyEvent(
            PySide2.QtCore.QEvent.Type.KeyPress,
            int(key),  # type: ignore[call-overload]
            PySide2.QtCore.Qt.KeyboardModifiers(),
            0,
            0,
            0
        )
        self.do_process_key_event(event)

    def do_release_key(self, key: PySide2.QtCore.Qt.Key) -> None:
        event = PySide2.QtGui.QKeyEvent(
            PySide2.QtCore.QEvent.Type.KeyRelease,
            int(key),  # type: ignore[call-overload]
            PySide2.QtCore.Qt.KeyboardModifiers(),
            0,
            0,
            0,
        )
        self.do_process_key_event(event)

    def do_key(self, key: PySide2.QtCore.Qt.Key) -> None:
        self.do_press_key(key)
        self.do_release_key(key)

    def test_on_changed_prints_sequence(self) -> None:
        self.do_key(PySide2.QtCore.Qt.Key.Key_A)
        self.assertEqual(self.input.text(), 'A')
        self.do_key(PySide2.QtCore.Qt.Key.Key_B)
        self.assertEqual(self.input.text(), 'A; B')

    def test_on_changed_prints_trigger_to_activate_if_any(self) -> None:
        self.do_key(PySide2.QtCore.Qt.Key.Key_A)
        self.do_key(PySide2.QtCore.Qt.Key.Key_B)
        self.do_key(PySide2.QtCore.Qt.Key.Key_C)
        self.assertEqual(self.input.text(), 'A; B; C: alphabet')

    def test_on_changed_prints_undefined_sequence(self) -> None:
        self.do_key(PySide2.QtCore.Qt.Key.Key_B)
        self.assertEqual(self.input.text(), 'B is undefined.')
        self.do_key(PySide2.QtCore.Qt.Key.Key_A)
        self.do_key(PySide2.QtCore.Qt.Key.Key_A)
        self.assertEqual(self.input.text(), 'A; A is undefined.')

    def test_on_changed_resets_text_on_reset(self) -> None:
        self.do_key(PySide2.QtCore.Qt.Key.Key_B)
        self.assertEqual(self.input.text(), 'B is undefined.')
        self.input.reset_pressed_sequence()
        self.assertEqual(self.input.text(), '')

    def test_on_changed_activates_trigger(self) -> None:
        self.do_key(PySide2.QtCore.Qt.Key.Key_A)
        self.do_key(PySide2.QtCore.Qt.Key.Key_B)
        self.do_key(PySide2.QtCore.Qt.Key.Key_C)
        self.assertTrue(self.alphabet_event.is_set())

    def test_on_changed_does_not_raise_if_trigger_not_bound(
        self
    ) -> None:
        self.trigger_registry.unbind('alphabet')
        self.do_key(PySide2.QtCore.Qt.Key.Key_A)
        self.do_key(PySide2.QtCore.Qt.Key.Key_B)
        self.do_key(PySide2.QtCore.Qt.Key.Key_C)
        self.assertFalse(self.alphabet_event.is_set())


class TestTriggerControlled(
    UsesQApplication, UsesRegistry, UsesExecutor, UsesCapabilities,
    unittest.TestCase
):
    """Tests :class:`~phile.hotkey.pyside2.TriggerControlled`."""

    def setUp(self) -> None:
        super().setUp()

        class TriggerControlledWidget(
            phile.hotkey.pyside2.TriggerControlled,
            PySide2.QtWidgets.QWidget,
        ):
            pass

        self.trigger_controlled = TriggerControlledWidget(
            capabilities=self.capabilities
        )
        self.addCleanup(self.trigger_controlled.deleteLater)

    def test_init_binds_triggers(self) -> None:
        registry = self.trigger_registry
        self.assertTrue(registry.is_shown('phile.hotkey.pyside2.show'))
        self.assertTrue(registry.is_bound('phile.hotkey.pyside2.hide'))

    def test_close_unbinds_triggers(self) -> None:
        registry = self.trigger_registry
        self.trigger_controlled.close()
        self.assertFalse(registry.is_bound('phile.hotkey.pyside2.show'))
        self.assertFalse(registry.is_bound('phile.hotkey.pyside2.hide'))

    def test_show_hide_toggles_triggers(self) -> None:
        trigger_controlled = self.trigger_controlled
        registry = self.trigger_registry
        self.assertTrue(trigger_controlled.isHidden())
        self.assertTrue(registry.is_shown('phile.hotkey.pyside2.show'))
        self.assertFalse(registry.is_shown('phile.hotkey.pyside2.hide'))
        trigger_controlled.show()
        self.assertFalse(registry.is_shown('phile.hotkey.pyside2.show'))
        self.assertTrue(registry.is_shown('phile.hotkey.pyside2.hide'))
        trigger_controlled.hide()
        self.assertTrue(registry.is_shown('phile.hotkey.pyside2.show'))
        self.assertFalse(registry.is_shown('phile.hotkey.pyside2.hide'))
