#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import functools
import sys

# Internal packages.
import phile
import phile.capability
import phile.configuration
import phile.cmd
import phile.launcher
import phile.launcher.cmd


async def async_run(
    capability_registry: phile.capability.Registry,
) -> int:  # pragma: no cover
    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        launcher_name := 'phile.launcher.cmd',
        phile.launcher.Descriptor(
            after={'phile.launcher'},
            binds_to={'phile.launcher'},
            exec_start=[
                functools.partial(
                    phile.cmd.async_cmdloop_threaded_stdin,
                    phile.launcher.cmd.Cmd(
                        launcher_registry=launcher_registry,
                    ),
                ),
            ],
        )
    )
    state_machine = launcher_registry.state_machine
    start = state_machine.start
    await start('phile.configuration')
    configurations = capability_registry[phile.configuration.Entries]
    await asyncio.gather(
        *(start(name) for name in configurations.main_autostart),
        start('phile.launcher.cmd'),
        return_exceptions=True,
    )
    # pylint: disable=protected-access
    running_tasks = state_machine._running_tasks
    try:
        cmd_task = running_tasks[launcher_name]
    except KeyError:
        return 1
    await cmd_task
    return 0


def main() -> int:  # pragma: no cover
    with contextlib.suppress(asyncio.CancelledError, KeyboardInterrupt):
        return phile.main.run(async_run)
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
