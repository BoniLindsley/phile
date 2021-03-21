#!/usr/bin/env python3
"""
----------------------
Global hotkey handling
----------------------
"""

# Standard libraries.
import collections.abc
import contextlib
import sys
import typing

# External dependencies.
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


def run(capabilities: phile.Capabilities) -> int:  # pragma: no cover
    configuration = capabilities[phile.Configuration]
    trigger_registry = capabilities[phile.trigger.Registry]

    hotkey_map: typing.Optional[dict[str, typing.Any]] = None
    hotkey_config = configuration.data.get('hotkey')
    if hotkey_config is not None:
        hotkey_map = hotkey_config.get('global map')
    if hotkey_map is None:
        return 1
    keymap: dict[tuple[Button, ...], str] = {
        tuple(pynput.keyboard.HotKey.parse(keys)): trigger
        for keys, trigger in hotkey_map.items()
    }
    state: list[Button] = []
    listener: pynput.keyboard.Listener

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

    def stop() -> None:
        raise pynput.keyboard.Listener.StopException()

    with phile.trigger.Provider(
        callback_map={_loader_name + '.stop': stop},
        registry=trigger_registry,
    ) as provider, pynput.keyboard.Listener(
        capabilities=capabilities,
        on_press=on_press,
        on_release=on_release,
    ) as listener:
        provider.show_all()
        listener.join()
    return 0


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    if argv is None:
        argv = sys.argv
    with contextlib.suppress(KeyboardInterrupt):
        capabilities = phile.Capabilities()
        capabilities.set(phile.Configuration())
        trigger_registry = phile.trigger.Registry()
        capabilities.set(trigger_registry)
        trigger_registry.event_callback_map.append(
            lambda method, _registry, trigger_name:
            print(trigger_name, method.__name__)
        )
        return run(capabilities=capabilities)
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
