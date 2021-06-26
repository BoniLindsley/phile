#!/usr/bin/env python3

# Internal packages.
import phile.configuration
import phile.notify
import phile.tray
import phile.tray.watchdog
import phile.watchdog.asyncio

default_tray_entry = phile.tray.Entry(
    name='30-phile-notify-tray', text_icon=' N'
)


async def run(
    *,
    configuration: phile.configuration.Entries,
    observer: phile.watchdog.asyncio.BaseObserver,
    tray_entry: phile.tray.Entry = default_tray_entry,
    tray_target: phile.tray.watchdog.Target,
) -> None:
    notify_directory = (
        configuration.state_directory_path /
        configuration.notification_directory
    )
    notify_suffix = configuration.notification_suffix
    notify_directory.mkdir(parents=True, exist_ok=True)
    try:
        notify_sorter = phile.data.SortedLoadCache[phile.notify.File](
            create_file=phile.notify.File,
            on_insert=lambda _1, _2, _3: tray_target.set(tray_entry),
            on_pop=(
                lambda _1, _2, tracked_data: None
                if tracked_data else tray_target.pop(tray_entry.name)
            ),
        )
        try:
            notify_sorter.refresh(
                data_directory=notify_directory,
                data_file_suffix=configuration.notification_suffix
            )
            watchdog_view = await observer.schedule(notify_directory)
            try:
                async for path, exists in (  # pragma: no branch
                    phile.watchdog.asyncio.monitor_file_existence(
                        directory_path=notify_directory,
                        expected_suffix=notify_suffix,
                        watchdog_view=watchdog_view,
                    )
                ):
                    del exists
                    notify_sorter.update(path)
            finally:
                await watchdog_view.aclose()
        finally:
            notify_sorter.tracked_data.clear()
    finally:
        tray_target.pop(tray_entry.name)
