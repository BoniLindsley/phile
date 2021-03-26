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


async def async_provide_async_tmux_client(
    capability_registry: phile.capability.Registry,
    ready: asyncio.Event,
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
        await asyncio.Event().wait()
    assert False, 'Unreaachable code'
