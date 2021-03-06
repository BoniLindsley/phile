#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import functools
import sys
import typing

# External dependencies.
import watchdog.observers

# Internal packages.
import phile
import phile.notify
import phile.tray
import phile.watchdog
import phile.watchdog.observers


async def run(capabilities: phile.Capabilities) -> None:
    configuration = capabilities[phile.Configuration]
    watching_observer = capabilities[watchdog.observers.api.BaseObserver]
    with contextlib.ExitStack() as exit_stack:
        notify_tray_file = phile.tray.File.from_path_stem(
            configuration=configuration,
            path_stem='30-phile-notify-tray',
            text_icon=' N'
        )
        exit_stack.callback(
            notify_tray_file.path.unlink, missing_ok=True
        )
        refresh_event = asyncio.Event()
        notify_sorter = (
            phile.data.SortedLoadCache[phile.notify.File](
                create_file=phile.notify.File,
                on_insert=lambda _1, _2, _3: refresh_event.set(),
                on_pop=lambda _1, _2, _3: refresh_event.set(),
            )
        )
        exit_stack.callback(notify_sorter.tracked_data.clear)
        exit_stack.enter_context(
            phile.watchdog.Scheduler(
                path_filter=functools.partial(
                    phile.notify.File.check_path,
                    configuration=configuration
                ),
                path_handler=functools.partial(
                    asyncio.get_running_loop().call_soon_threadsafe,
                    notify_sorter.update
                ),
                watched_path=configuration.notification_directory,
                watching_observer=watching_observer,
            )
        )
        notify_sorter.refresh(
            data_directory=configuration.notification_directory,
            data_file_suffix=configuration.notification_suffix
        )
        while True:
            await refresh_event.wait()
            refresh_event.clear()
            if notify_sorter.tracked_data:
                notify_tray_file.save()
            else:
                notify_tray_file.path.unlink(missing_ok=True)


async def async_main(argv: typing.List[str]) -> int:  # pragma: no cover
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    async with phile.watchdog.observers.async_open() as observer:
        capabilities[watchdog.observers.api.BaseObserver] = observer
        await run(capabilities=capabilities)
    return 0


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
