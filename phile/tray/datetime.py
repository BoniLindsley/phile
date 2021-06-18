#!/usr/bin/env python3

# Standard library.
import asyncio
import datetime

# Internal packages.
import phile.tray
import phile.tray.watchdog

default_refresh_interval = datetime.timedelta(seconds=5)


async def run(
    *,
    refresh_interval: datetime.timedelta = default_refresh_interval,
    tray_name: str = '90-phile-tray-datetime',
    tray_target: phile.tray.watchdog.Target,
) -> None:
    tray_entry = phile.tray.Entry(name=tray_name)
    tray_target.set(entry=tray_entry)
    try:

        def update_file() -> datetime.timedelta:
            now = datetime.datetime.now()
            tray_entry.text_icon = now.strftime(' %Y-%m-%dw%w %H:%M')
            tray_target.set(entry=tray_entry)
            return datetime.timedelta(
                seconds=60 - now.second + 1 - now.microsecond / 1_000_000
            )

        wait_seconds = refresh_interval.total_seconds()
        while True:
            wait_timedelta = await asyncio.to_thread(update_file)
            await asyncio.sleep(wait_timedelta.total_seconds())
    finally:
        tray_target.pop(name=tray_name)
