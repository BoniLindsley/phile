#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import os
import typing

# Internal packages.
import phile
import phile.asyncio
import phile.capability
import phile.capability.asyncio
import phile.tmux.control_mode


def _is_inside_tmux() -> bool:
    return 'TMUX' in os.environ


def is_available() -> bool:
    return _is_inside_tmux()


async def _async_provide_async_tmux_client(
    capability_registry: phile.capability.Registry,
) -> None:
    async with contextlib.AsyncExitStack() as stack:
        control_mode = await stack.enter_async_context(
            phile.tmux.control_mode.open(
                control_mode_arguments=(
                    phile.tmux.control_mode.Arguments()
                )
            )
        )
        stack.enter_context(
            capability_registry.provide(
                control_mode, phile.tmux.control_mode.Client
            )
        )
        await stack.enter_async_context(
            phile.asyncio.open_task(control_mode.run())
        )
        asyncio.get_running_loop().stop()
        await asyncio.Event().wait()
    assert False, 'Unreachable code'  # pragma: no cover


def provide_async_tmux_client(
    capability_registry: phile.capability.Registry
) -> contextlib.AbstractContextManager[typing.Any]:
    loop = phile.capability.asyncio.get_instance(capability_registry)
    assert not loop.is_closed()
    assert not loop.is_running()
    client_task = loop.create_task(
        _async_provide_async_tmux_client(capability_registry)
    )
    loop.run_forever()

    with contextlib.ExitStack() as stack:
        # This is to ensure a reference to the task is kept alive
        # so that the task would not be cancelled.
        # Futhuremore, if the context manager goes out of scop,
        # and the task is not referenced elsewhere,
        # the task would be cancelled as clean-up.
        # However, that requires the loop to run for clean-up.
        # Whether the loop should be running depends on the user.
        stack.callback(client_task.done)
        return stack.pop_all()
    assert False, 'Unreachable code'  # pragma: no cover
