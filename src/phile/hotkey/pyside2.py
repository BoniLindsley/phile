#!/usr/bin/env python3
"""
-------------------
GUI hotkey handling
-------------------
"""

# Standard libraries.
import asyncio
import collections.abc
import contextlib
import functools
import itertools
import typing

# External dependencies.
import PySide2.QtCore
import PySide2.QtGui
import PySide2.QtWidgets

# Internal modules.
import phile.configuration
import phile.PySide2.QtCore
import phile.trigger
import phile.trigger.pyside2

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]

Key = PySide2.QtCore.Qt.Key
ordered_modifiers = (
    Key.Key_Meta,  # Triggered by Shift+Alt in that order?
    Key.Key_Super_L,
    Key.Key_Super_R,
    Key.Key_Control,
    Key.Key_Alt,
    Key.Key_AltGr,
    Key.Key_Shift,
)
"""Order of modifiers as prefix of key strings."""
ordered_modifier_values = list(
    int(key) for key in ordered_modifiers  # type: ignore[call-overload]
)
"""Order of modifiers values as prefix of key strings."""
modifier_values = set(
    int(key) for key in ordered_modifiers  # type: ignore[call-overload]
)
"""Keys that do not force a key map check when pressed."""
key_conversion: dict[str, str] = {
    "Ctrl": "Control",
    "Esc": "Escape",
}
"""Alternative print names of some keys"""
key_display_name: dict[str, str] = {
    "Control": "Ctrl",
    "Escape": "Esc",
}

qt_modifier_values: (
    dict[PySide2.QtCore.Qt.KeyboardModifier, list[int]]
) = {
    PySide2.QtCore.Qt.AltModifier: [
        int(Key.Key_Alt),  # type: ignore[call-overload]
    ],
    PySide2.QtCore.Qt.ControlModifier: [
        int(Key.Key_Control),  # type: ignore[call-overload]
    ],
    PySide2.QtCore.Qt.MetaModifier: [
        int(Key.Key_Super_L),  # type: ignore[call-overload]
        int(Key.Key_Super_R),  # type: ignore[call-overload]
    ],
    PySide2.QtCore.Qt.ShiftModifier: [
        int(Key.Key_Shift),  # type: ignore[call-overload]
    ],
}


def key_value_from_string(key_name: str) -> int:
    key_name = key_name.strip().removeprefix("<").removesuffix(">")
    canonical_name = key_conversion.get(key_name, key_name)
    return int(getattr(PySide2.QtGui.Qt, "Key_" + canonical_name))


def key_combination_from_string(
    combination_name: str,
) -> tuple[int, ...]:
    return tuple(
        sorted(
            key_value_from_string(key_name)
            for key_name in combination_name.split("+")
        )
    )


def key_sequence_from_string(
    sequence_name: str,
) -> tuple[tuple[int, ...], ...]:
    combination_names = (key.strip() for key in sequence_name.split(";"))
    return tuple(
        key_combination_from_string(name) for name in combination_names
    )


def order_key_sequence(
    key_combination: collections.abc.Iterable[int],
) -> collections.abc.Iterator[int]:
    key_values = sorted(key_combination)
    return itertools.chain(
        filter(key_values.__contains__, ordered_modifier_values),
        itertools.filterfalse(modifier_values.__contains__, key_values),
    )


def key_value_to_string(value: int) -> str:
    key = Key(value)  # type: ignore[call-arg]
    key_name: bytes = key.name  # type: ignore[attr-defined]
    as_string = key_name.removeprefix(b"Key_").decode()
    as_string = key_display_name.get(as_string, as_string)
    return as_string


def key_combination_to_string(
    combination: collections.abc.Iterable[int],
) -> str:
    return "+".join(
        key_value_to_string(value)
        for value in order_key_sequence(combination)
    )


def key_sequence_to_string(
    sequence: collections.abc.Iterable[tuple[int, ...]]
) -> str:
    return "; ".join(
        key_combination_to_string(combination)
        for combination in sequence
    )


class PressedKeys:
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        # Pylint is ignoring the type cast.
        assert widget.isWidgetType()  # pylint: disable=no-member
        self.pressed_keys = set[int]()

    def hideEvent(self, event: PySide2.QtGui.QHideEvent) -> None:
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        # Pylint is ignoring the type cast.
        widget.hideEvent(event)  # pylint: disable=no-member
        for key in self.pressed_keys.copy():
            self.keyReleaseEvent(
                PySide2.QtGui.QKeyEvent(
                    PySide2.QtCore.QEvent.Type.KeyRelease,
                    key,
                    PySide2.QtCore.Qt.KeyboardModifiers(),
                    0,
                    0,
                    0,
                ),
            )

    def keyPressEvent(self, event: PySide2.QtGui.QKeyEvent) -> None:
        if not self.update_pressed_key(event):
            widget = typing.cast(PySide2.QtWidgets.QWidget, super())
            # Pylint is ignoring the type cast.
            widget.keyPressEvent(event)  # pylint: disable=no-member

    def keyReleaseEvent(self, event: PySide2.QtGui.QKeyEvent) -> None:
        is_event_handled = self.update_pressed_key(event)
        if not is_event_handled:
            widget = typing.cast(PySide2.QtWidgets.QWidget, super())
            # Pylint is ignoring the type cast.
            widget.keyReleaseEvent(event)  # pylint: disable=no-member

    def update_pressed_key(self, event: PySide2.QtGui.QKeyEvent) -> bool:
        is_pressed_keys_changed = False
        if self.is_useful_key_event(event):
            event_type = event.type()
            if event_type == PySide2.QtCore.QEvent.Type.KeyPress:
                self.pressed_keys.add(event.key())
                is_pressed_keys_changed = True
            if event_type == PySide2.QtCore.QEvent.Type.KeyRelease:
                self.pressed_keys.discard(event.key())
                is_pressed_keys_changed = True
            self.update_pressed_modifiers(event)
        if is_pressed_keys_changed:
            self.on_pressed_keys_changed(event)
        return is_pressed_keys_changed

    def update_pressed_modifiers(
        self,
        event: PySide2.QtGui.QKeyEvent,
    ) -> None:
        if event.type() != PySide2.QtCore.QEvent.Type.KeyPress:
            return
        pressed_keys = self.pressed_keys
        pressed_modifiers = event.modifiers()
        for modifier, key_values in qt_modifier_values.items():
            if pressed_modifiers & modifier:  # type: ignore[operator]
                if pressed_keys.isdisjoint(key_values):
                    pressed_keys.add(key_values[0])
            else:
                pressed_keys.difference_update(key_values)

    def on_pressed_keys_changed(
        self, event: PySide2.QtGui.QKeyEvent
    ) -> None:
        del event

    def is_useful_key_event(
        self, event: PySide2.QtGui.QKeyEvent
    ) -> bool:
        key = event.key()
        return (
            (not event.isAutoRepeat())
            and bool(key)
            and (key != PySide2.QtCore.Qt.Key_unknown)
        )


class PressedKeySequence(PressedKeys):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.pressed_sequence: list[tuple[int, ...]] = []
        """Key sequence so far, excluding the currently pressed keys."""
        self.key_bindings: dict[tuple[int, ...], typing.Any] = {}
        """Key sequences to wait for."""
        self.active_binding = self.key_bindings
        """Key map for the key sequence so far."""

    def on_pressed_keys_changed(
        self, event: PySide2.QtGui.QKeyEvent
    ) -> None:
        if event.type() == PySide2.QtCore.QEvent.Type.KeyRelease:
            return
        if not self.active_binding or not self.pressed_sequence:
            self.active_binding = self.key_bindings
            self.pressed_sequence.clear()
        key_combination = tuple(sorted(self.pressed_keys))
        bound_value = self.active_binding.get(key_combination)
        if bound_value is None and event.key() in modifier_values:
            return
        self.pressed_sequence.append(key_combination)
        self.on_pressed_sequence_changed(bound_value)

    def reset_pressed_sequence(self) -> None:
        self.active_binding = self.key_bindings
        self.pressed_sequence.clear()
        self.on_pressed_sequence_changed(None)

    def on_pressed_sequence_changed(
        self, bound_value: typing.Any
    ) -> None:
        self.active_binding = (
            bound_value if isinstance(bound_value, dict) else {}
        )

    def add_key_bindings(self, key_map: dict[str, str]) -> None:
        for key_sequence, trigger in key_map.items():
            key_combinations = key_sequence_from_string(key_sequence)
            sub_maps = [self.key_bindings]
            for key_value in key_combinations:
                sub_map = sub_maps[-1].setdefault(key_value, {})
                sub_maps.append(sub_map)
            sub_maps[-2][key_combinations[-1]] = trigger


class HotkeyInput(PressedKeySequence, PySide2.QtWidgets.QLabel):
    def __init__(
        self,
        *args: typing.Any,
        trigger_registry: phile.trigger.Registry,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._trigger_registry = trigger_registry

    def on_pressed_sequence_changed(
        self, bound_value: typing.Any
    ) -> None:
        super().on_pressed_sequence_changed(bound_value)
        shown_text = key_sequence_to_string(self.pressed_sequence)
        target: typing.Optional[str] = None
        if shown_text and bound_value is None:
            shown_text += " is undefined."
        elif isinstance(bound_value, str):
            target = bound_value
            shown_text += ": " + target
        self.setText(shown_text)
        if target is not None:
            with contextlib.suppress(phile.trigger.Registry.NotBound):
                self._trigger_registry.activate_if_shown(target)


# A little difficult to test this.
# Using layout triggers warnings in stdout logs.
# Should be okay to not test this,
# since it is just a wrapper window to use a widget.
class HotkeyDialog(
    phile.trigger.pyside2.TriggerControlled, PySide2.QtWidgets.QDialog
):  # pragma: no cover
    def __init__(
        self,
        *args: typing.Any,
        configurations: phile.configuration.Entries,
        trigger_registry: phile.trigger.Registry,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(
            *args,
            trigger_prefix=_loader_name,
            trigger_registry=trigger_registry,
            **kwargs,
        )
        self.setLayout(layout := PySide2.QtWidgets.QGridLayout(self))
        self.hotkey_widget = HotkeyInput(
            self,
            trigger_registry=trigger_registry,
        )
        layout.addWidget(self.hotkey_widget)
        self.setWindowFlag(PySide2.QtCore.Qt.WindowStaysOnTopHint)
        self.hotkey_widget.add_key_bindings(configurations.hotkey_map)
        self.hotkey_widget.setFocus(
            PySide2.QtCore.Qt.FocusReason.OtherFocusReason
        )

    def hideEvent(self, event: PySide2.QtGui.QHideEvent) -> None:
        super().hideEvent(event)
        self.hotkey_widget.reset_pressed_sequence()


async def run(
    *,
    configurations: phile.configuration.Entries,
    pyside2_executor: phile.PySide2.QtCore.Executor,
    trigger_registry: phile.trigger.Registry,
) -> None:  # pragma: no cover
    loop = asyncio.get_running_loop()
    dialog_closed = asyncio.Event()
    dialog = await asyncio.wrap_future(
        pyside2_executor.submit(
            HotkeyDialog,
            configurations=configurations,
            pyside2_executor=pyside2_executor,
            trigger_registry=trigger_registry,
        )
    )
    try:

        def set_closed_event(
            qobject: typing.Optional[PySide2.QtCore.QObject] = None,
        ) -> None:
            del qobject
            loop.call_soon_threadsafe(dialog_closed.set)

        def on_start() -> None:
            dialog.destroyed.connect(set_closed_event)
            dialog.setAttribute(PySide2.QtCore.Qt.WA_DeleteOnClose)
            dialog.show()

        phile.PySide2.QtCore.call_soon_threadsafe(on_start)
        await dialog_closed.wait()
    except:

        def delete_dialog() -> None:
            """Ensure close events are emitted before deleting."""
            dialog.close()
            dialog.deleteLater()

        phile.PySide2.QtCore.call_soon_threadsafe(delete_dialog)
        raise
