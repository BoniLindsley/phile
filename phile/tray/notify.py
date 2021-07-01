#!/usr/bin/env python3

# Internal packages.
import phile.notify
import phile.tray
import phile.tray.watchdog

default_tray_entry = phile.tray.Entry(
    name='30-phile-notify-tray', text_icon=' N'
)


async def run(
    *,
    notify_registry: phile.notify.Registry,
    tray_entry: phile.tray.Entry = default_tray_entry,
    tray_target: phile.tray.watchdog.Target,
) -> None:
    try:
        notify_view = notify_registry.event_queue.__aiter__()
        if notify_registry.current_keys:
            tray_target.set(tray_entry)
        # Branch of not iterating.
        # Covered in test_stops_gracefully_if_notify_registry_closes.
        # Not sure why it is not picked up by coverage.py.
        async for notify_event in notify_view:  # pragma: no branch
            if notify_event.current_keys:
                tray_target.set(tray_entry)
            else:
                tray_target.pop(tray_entry.name)
    finally:
        tray_target.pop(tray_entry.name)
