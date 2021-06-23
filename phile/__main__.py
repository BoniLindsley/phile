#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import logging
import sys

# Internal packages.
import phile.configuration
import phile.launcher
import phile.launcher.cmd
import phile.main


async def async_run(
    launcher_registry: phile.launcher.Registry,
) -> int:  # pragma: no cover
    start = launcher_registry.start
    await start('phile.configuration')
    configurations = (
        launcher_registry.capability_registry[phile.configuration.Entries
                                              ]
    )
    event_publisher = (
        launcher_registry.event_publishers[phile.launcher.Registry.stop]
    )
    event_view = event_publisher.__aiter__()
    del event_publisher
    await asyncio.gather(
        *(start(name) for name in configurations.main_autostart),
        start(cmd_name := 'phile.launcher.cmd'),
        return_exceptions=True,
    )
    if not launcher_registry.is_running(cmd_name):
        return 1
    async for event in event_view:
        if event == cmd_name:
            break
    return 0


def main() -> int:  # pragma: no cover
    with contextlib.suppress(asyncio.CancelledError, KeyboardInterrupt):
        return phile.main.run(async_run)
    return 0


if __name__ == '__main__':  # pragma: no cover
    if __debug__:
        log_level = logging.DEBUG
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelno)03d] %(name)s:'
            ' %(message)s',
        )
        handler.setFormatter(formatter)
        handler.setLevel(log_level)
        package_logger = logging.getLogger('phile')
        package_logger.addHandler(handler)
        package_logger.setLevel(1)
    sys.exit(main())
