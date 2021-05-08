#!/usr/bin/env python3
"""
----------------------
Global hotkey handling
----------------------
"""

# Standard libraries.
import collections.abc
import contextlib
import typing

# External dependencies.
import pynput  # type: ignore[import]

# Internal modules.
import phile.asyncio
import phile.configuration
import phile.trigger

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]

Button = typing.Union[pynput.keyboard.Key, pynput.keyboard.KeyCode]
ButtonCallback = (
    collections.abc.Callable[[typing.Optional[Button]], typing.Any]
)


class _Listener(
    phile.asyncio.Thread,
    pynput.keyboard.Listener,  # type: ignore[misc]
):
    pass


async def run(
    configuration: phile.configuration.Entries,
    trigger_registry: phile.trigger.Registry,
) -> int:  # pragma: no cover
    keymap: dict[tuple[Button, ...], str] = {
        tuple(pynput.keyboard.HotKey.parse(keys)): trigger
        for keys, trigger in configuration.hotkey_global_map.items()
    }
    listener: _Listener
    state: list[Button] = []

    def on_press(button: typing.Optional[Button]) -> None:
        if button is None:
            return
        button = listener.canonical(button)
        state.append(button)
        print(state, button)
        trigger = keymap.get(tuple(state))
        if trigger is not None:
            with contextlib.suppress(phile.trigger.Registry.NotBound):
                trigger_registry.activate_if_shown(trigger)

    def on_release(button: typing.Optional[Button]) -> None:
        if button is None:
            return
        button = listener.canonical(button)
        with contextlib.suppress(ValueError):
            state.remove(button)

    listener = _Listener(on_press=on_press, on_release=on_release)
    listener.start()
    try:
        await listener.async_join()
    finally:
        listener.stop()
        await listener.async_join()
    return 0
