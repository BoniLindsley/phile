#!/usr/bin/env python3
"""
-----------------------------------------
Floating tray window using :mod:`tkinter`
-----------------------------------------
"""

# Standard libraries.
import functools
import sys
import tkinter
import typing

# External dependencies.
import watchdog.observers

# Internal packages.
import phile
import phile.data
import phile.tray
import phile.watchdog.observers


def run(capabilities: phile.Capabilities) -> int:  # pragma: no cover
    configuration = capabilities[phile.Configuration]
    watching_observer = capabilities[watchdog.observers.api.BaseObserver]
    root = tkinter.Tk()
    root.attributes('-topmost', True)
    label = tkinter.Label(root)
    label.pack(side='left')
    label['font'] = '{courier}'

    sorter_handler: phile.data.UpdateCallback[phile.tray.File] = (
        lambda _index, _tray_file, tracked_data: label.__setitem__(
            'text',
            phile.tray.files_to_text(tracked_data),
        )
    )
    tray_sorter = phile.data.SortedLoadCache[phile.tray.File](
        create_file=phile.tray.File,
        on_insert=sorter_handler,
        on_pop=sorter_handler,
        on_set=sorter_handler,
    )
    # Start monitoring to not miss file events.
    with phile.watchdog.Scheduler(
        path_filter=functools.partial(
            phile.tray.File.check_path, configuration=configuration
        ),
        path_handler=tray_sorter.update,
        watched_path=configuration.tray_directory,
        watching_observer=watching_observer,
    ):
        # Update all existing tray files.
        tray_sorter.refresh(
            data_directory=configuration.tray_directory,
            data_file_suffix=configuration.tray_suffix
        )

        root.mainloop()
    return 0


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    with phile.watchdog.observers.open(
    ) as (capabilities[watchdog.observers.api.BaseObserver]):
        run(capabilities=capabilities)
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
