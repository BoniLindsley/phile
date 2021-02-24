#!/usr/bin/env python3
"""
--------------------------
Global GUI hotkey handling
--------------------------
"""

# Standard libraries.
import asyncio
import collections.abc
import contextlib
import functools
import pathlib
import sys
import threading
import types
import typing

# External dependencies.
import portalocker  # type: ignore[import]
import pynput  # type: ignore[import]

# Internal modules.
import phile
import phile.asyncio
import phile.trigger
import phile.watchdog

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]

Button = typing.Union[pynput.keyboard.Key, pynput.keyboard.KeyCode]
ButtonCallback = collections.abc.Callable[[typing.Optional[Button]],
                                          typing.Any]


class AsyncKeyboardListener(
    phile.asyncio.Thread,
    pynput.keyboard.Listener,  # type: ignore[misc]
):
    pass


async def run(
    capabilities: phile.Capabilities
) -> int:  # pragma: no cover
    configuration = capabilities[phile.Configuration]
    trigger_registry = capabilities[phile.trigger.Registry]

    keymap_source = configuration.data.get('hotkey')
    if keymap_source is None:
        return 1
    keymap: dict[tuple[Button, ...], str] = {
        tuple(pynput.keyboard.HotKey.parse(keys)): trigger
        for keys, trigger in keymap_source.items()
    }
    state: list[Button] = []
    listener: AsyncKeyboardListener

    def on_press(button: typing.Optional[Button]) -> None:
        if button is None:
            return
        button = listener.canonical(button)
        state.append(button)
        trigger = keymap.get(tuple(state))
        if trigger is not None:
            trigger_registry.activate_if_shown(trigger)

    def on_release(button: typing.Optional[Button]) -> None:
        if button is None:
            return
        button = listener.canonical(button)
        with contextlib.suppress(ValueError):
            state.remove(button)

    def stop() -> None:
        raise AsyncKeyboardListener.StopException()

    with phile.trigger.Provider(
        callback_map={_loader_name + '.stop': stop},
        registry=trigger_registry,
        show_all=True,
    ), AsyncKeyboardListener(
        capabilities=capabilities,
        on_press=on_press,
        on_release=on_release,
    ) as listener:
        await listener.async_join()
    return 0


async def async_main(argv: list[str]) -> int:  # pragma: no cover
    del argv
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    trigger_registry = phile.trigger.Registry()
    capabilities.set(trigger_registry)
    trigger_registry.event_callback_map.append(
        lambda method, _registry, trigger_name:
        print(trigger_name, method.__name__)
    )
    await run(capabilities=capabilities)
    return 0


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    if argv is None:
        argv = sys.argv
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
