#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import logging
import sys

# Internal packages.
import phile.capability
import phile.configuration
import phile.launcher
import phile.launcher.cmd
import phile.main


async def async_run(
    capability_registry: phile.capability.Registry,
) -> int:  # pragma: no cover
    state_machine = (
        capability_registry[phile.launcher.Registry].state_machine
    )
    start = state_machine.start
    await start('phile.configuration')
    configurations = capability_registry[phile.configuration.Entries]
    await asyncio.gather(
        *(start(name) for name in configurations.main_autostart),
        start(cmd_name := 'phile.launcher.cmd'),
        return_exceptions=True,
    )
    try:
        # pylint: disable=protected-access
        cmd_task = state_machine._running_tasks[cmd_name]
    except KeyError:
        return 1
    await cmd_task
    return 0


def main() -> int:  # pragma: no cover
    with contextlib.suppress(asyncio.CancelledError, KeyboardInterrupt):
        return phile.main.run(async_run)
    return 0


if __name__ == '__main__':  # pragma: no cover
    if __debug__:
        logging.basicConfig(
            handlers=[logging.StreamHandler()], level=logging.DEBUG
        )
    sys.exit(main())
