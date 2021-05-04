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
import sys
import threading
import typing

# External dependencies.
import PySide2.QtCore
import PySide2.QtGui
import PySide2.QtWidgets

# Internal modules.
import phile
import phile.PySide2.QtCore
import phile.tray.tmux
import phile.trigger

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
    'Ctrl': 'Control',
    'Esc': 'Escape',
}
"""Alternative print names of some keys"""
key_display_name: dict[str, str] = {
    'Control': 'Ctrl',
    'Escape': 'Esc',
}


def key_value_from_string(key_name: str) -> int:
    key_name = key_name.strip().removeprefix('<').removesuffix('>')
    canonical_name = key_conversion.get(key_name, key_name)
    return int(getattr(PySide2.QtGui.Qt, 'Key_' + canonical_name))


def key_combination_from_string(
    combination_name: str
) -> tuple[int, ...]:
    return tuple(
        sorted(
            key_value_from_string(key_name)
            for key_name in combination_name.split('+')
        )
    )


def key_sequence_from_string(
    sequence_name: str
) -> tuple[tuple[int, ...], ...]:
    combination_names = (key.strip() for key in sequence_name.split(';'))
    return tuple(
        key_combination_from_string(name) for name in combination_names
    )


def order_key_sequence(
    key_combination: collections.abc.Iterable[int]
) -> collections.abc.Iterator[int]:
    key_values = sorted(key_combination)
    return itertools.chain(
        filter(key_values.__contains__, ordered_modifier_values),
        itertools.filterfalse(modifier_values.__contains__, key_values),
    )


def key_value_to_string(value: int) -> str:
    key = Key(value)  # type: ignore[call-arg]
    key_name: bytes = key.name  # type: ignore[attr-defined]
    as_string = key_name.removeprefix(b'Key_').decode()
    as_string = key_display_name.get(as_string, as_string)
    return as_string


def key_combination_to_string(
    combination: collections.abc.Iterable[int]
) -> str:
    return '+'.join(
        key_value_to_string(value)
        for value in order_key_sequence(combination)
    )


def key_sequence_to_string(
    sequence: collections.abc.Iterable[tuple[int, ...]]
) -> str:
    return '; '.join(
        key_combination_to_string(combination)
        for combination in sequence
    )


class PressedKeys:

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        assert widget.isWidgetType()
        self.pressed_keys = set[int]()

    def keyPressEvent(self, event: PySide2.QtGui.QKeyEvent) -> None:
        if not self.update_pressed_key(event):
            widget = typing.cast(PySide2.QtWidgets.QWidget, super())
            widget.keyPressEvent(event)

    def keyReleaseEvent(self, event: PySide2.QtGui.QKeyEvent) -> None:
        is_event_handled = self.update_pressed_key(event)
        if not is_event_handled:
            widget = typing.cast(PySide2.QtWidgets.QWidget, super())
            widget.keyReleaseEvent(event)

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
        if is_pressed_keys_changed:
            self.on_pressed_keys_changed(event)
        return is_pressed_keys_changed

    def on_pressed_keys_changed(
        self, event: PySide2.QtGui.QKeyEvent
    ) -> None:
        del event

    def is_useful_key_event(
        self, event: PySide2.QtGui.QKeyEvent
    ) -> bool:
        key = event.key()
        return (not event.isAutoRepeat(
        )) and bool(key) and (key != PySide2.QtCore.Qt.Key_unknown)


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
        capabilities: phile.Capabilities,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._trigger_registry = capabilities[phile.trigger.Registry]

    def on_pressed_sequence_changed(
        self, bound_value: typing.Any
    ) -> None:
        super().on_pressed_sequence_changed(bound_value)
        shown_text = key_sequence_to_string(self.pressed_sequence)
        target: typing.Optional[str] = None
        if shown_text and bound_value is None:
            shown_text += ' is undefined.'
        elif isinstance(bound_value, str):
            target = bound_value
            shown_text += ': ' + target
        self.setText(shown_text)
        if target is not None:
            with contextlib.suppress(phile.trigger.Registry.NotBound):
                self._trigger_registry.activate_if_shown(target)


class TriggerControlled:

    def __init__(
        self,
        *args: typing.Any,
        capabilities: phile.Capabilities,
        trigger_prefix: typing.Optional[str] = None,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        assert widget.isWidgetType()
        self._trigger_prefix = (
            _loader_name if trigger_prefix is None else trigger_prefix
        )
        executor = capabilities[phile.PySide2.QtCore.Executor]
        registry = capabilities[phile.trigger.Registry]
        self.trigger_producer = phile.trigger.Provider(
            callback_map={
                self._trigger_prefix + '.show':
                    functools.partial(executor.submit, widget.show),
                self._trigger_prefix + '.hide':
                    functools.partial(executor.submit, widget.hide),
            },
            registry=registry
        )
        self.trigger_producer.bind()
        self.trigger_producer.show(self._trigger_prefix + '.show')

    def closeEvent(self, event: PySide2.QtGui.QCloseEvent) -> None:
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        widget.closeEvent(event)
        self.trigger_producer.unbind()

    def hideEvent(self, event: PySide2.QtGui.QHideEvent) -> None:
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        widget.hideEvent(event)
        self.trigger_producer.hide(self._trigger_prefix + '.hide')
        self.trigger_producer.show(self._trigger_prefix + '.show')

    def showEvent(self, event: PySide2.QtGui.QShowEvent) -> None:
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        widget.showEvent(event)
        self.trigger_producer.hide(self._trigger_prefix + '.show')
        self.trigger_producer.show(self._trigger_prefix + '.hide')


# A little difficult to test this.
# Using layout triggers warnings in stdout logs.
# Should be okay to not test this,
# since it is just a wrapper window to use a widget.
class HotkeyDialog(
    TriggerControlled, PySide2.QtWidgets.QDialog
):  # pragma: no cover

    def __init__(
        self, *args: typing.Any, capabilities: phile.Capabilities,
        **kwargs: typing.Any
    ) -> None:
        super().__init__(*args, capabilities=capabilities, **kwargs)
        configuration = capabilities[phile.Configuration]
        self.setLayout(layout := PySide2.QtWidgets.QGridLayout(self))
        self.hotkey_widget = HotkeyInput(self, capabilities=capabilities)
        layout.addWidget(self.hotkey_widget)
        self.setWindowFlag(PySide2.QtCore.Qt.WindowStaysOnTopHint)
        hotkey_config = configuration.data.get('hotkey')
        if hotkey_config is not None:
            hotkey_map = hotkey_config.get('map')
            if hotkey_map is not None:
                self.hotkey_widget.add_key_bindings(hotkey_map)
        self.hotkey_widget.setFocus(
            PySide2.QtCore.Qt.FocusReason.OtherFocusReason
        )

    def hideEvent(self, event: PySide2.QtGui.QHideEvent) -> None:
        super().hideEvent(event)
        self.hotkey_widget.reset_pressed_sequence()


async def run(
    capabilities: phile.Capabilities,
) -> None:  # pragma: no cover
    # Ensure required capabilities are available.
    for capability in (
        phile.Configuration,
        phile.trigger.Registry,
        phile.PySide2.QtCore.Executor,
        PySide2.QtWidgets.QApplication,
    ):
        assert capability in capabilities, (
            "Capability not found: {}".format(capability)
        )
    executor = capabilities[phile.PySide2.QtCore.Executor]
    dialog = await asyncio.wrap_future(
        executor.submit(HotkeyDialog, capabilities=capabilities)
    )
    try:
        await asyncio.wrap_future(executor.submit(dialog.show))
        await asyncio.Event().wait()
    finally:
        await asyncio.wrap_future(executor.submit(dialog.close))


async def async_main(
    capabilities: phile.Capabilities,
) -> int:  # pragma: no cover
    qt_app = capabilities[PySide2.QtWidgets.QApplication]
    with phile.PySide2.QtCore.Executor() as executor:
        capabilities.set(executor)
        try:
            tasks: set[asyncio.Task[typing.Any]] = {
                asyncio.create_task(
                    phile.tray.tmux.read_byte(sys.stdin)
                ),
                asyncio.create_task(run(capabilities)),
            }
            await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            pending_tasks = asyncio.gather(*tasks)
            pending_tasks.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending_tasks
            await asyncio.wrap_future(executor.submit(qt_app.quit))
    return 0


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    del argv
    with contextlib.ExitStack() as stack:
        stack.enter_context(contextlib.suppress(KeyboardInterrupt))
        capabilities = phile.Capabilities()
        capabilities.set(phile.Configuration())
        capabilities.set(trigger_registry := phile.trigger.Registry())
        print('Press <Esc> in the GUI to hide.')
        print('Press <Return> in the terminal to exit.')
        trigger_registry.event_callback_map.append(
            lambda method, _registry, trigger_name:
            print(trigger_name, method.__name__)
        )
        del trigger_registry
        capabilities.set(qt_app := PySide2.QtWidgets.QApplication())
        qt_app.setQuitOnLastWindowClosed(False)
        threading.Thread(
            target=functools.partial(
                asyncio.run,
                async_main(capabilities),
            )
        ).start()
        qt_app.exec_()
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
