#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import dataclasses
import functools
import pathlib
import sys
import typing

# External dependencies.
import watchdog.observers  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.notify
import phile.tray
import phile.trigger
import phile.watchdog_extras


@dataclasses.dataclass
class Monitor:

    configuration: phile.configuration.Configuration
    watching_observer: watchdog.observers.Observer
    trigger_directory: pathlib.Path = pathlib.Path('phile-notify-tray')

    async def start(self) -> None:
        with contextlib.ExitStack() as exit_stack:
            configuration = self.configuration
            watching_observer = self.watching_observer
            call_soon_threadsafe = (
                asyncio.get_running_loop().call_soon_threadsafe
            )
            self.notify_tray_file = phile.tray.File.from_path_stem(
                configuration=configuration,
                path_stem='30-phile-notify-tray',
                text_icon=' N'
            )
            close_event = asyncio.Event()
            self.entry_point = exit_stack.enter_context(
                phile.trigger.EntryPoint(
                    callback_map={
                        'close': close_event.set,
                        'hide': self._hide,
                        'show': self._show,
                    },
                    configuration=configuration,
                    trigger_directory=self.trigger_directory,
                )
            )
            self.notify_sorter = (
                phile.data.SortedLoadCache[phile.notify.File](
                    create_file=phile.notify.File,
                    on_insert=self._refresh_tray_file,
                    on_pop=self._refresh_tray_file,
                )
            )
            self.trigger_scheduler = exit_stack.enter_context(
                phile.watchdog_extras.Scheduler(
                    path_filter=self.entry_point.check_path,
                    path_handler=functools.partial(
                        call_soon_threadsafe,
                        self.entry_point.activate_trigger
                    ),
                    watched_path=self.entry_point.trigger_directory,
                    watching_observer=watching_observer,
                )
            )
            self.notify_scheduler = phile.watchdog_extras.Scheduler(
                path_filter=functools.partial(
                    phile.notify.File.check_path,
                    configuration=configuration
                ),
                path_handler=functools.partial(
                    call_soon_threadsafe, self.notify_sorter.update
                ),
                watched_path=configuration.notification_directory,
                watching_observer=watching_observer,
            )
            exit_stack.callback(self._hide)
            # This has to be done after scheduling
            # so that its deletion will be detected.
            self.entry_point.add_trigger('close')
            self._show()
            await close_event.wait()

    def _show(self) -> None:
        configuration = self.configuration
        self.notify_scheduler.schedule()
        self.notify_sorter.refresh(
            data_directory=configuration.notification_directory,
            data_file_suffix=configuration.notification_suffix
        )
        self.entry_point.remove_trigger('show')
        self.entry_point.add_trigger('hide')

    def _hide(self) -> None:
        self.notify_scheduler.unschedule()
        self.notify_sorter.tracked_data.clear()
        self._remove_tray_file()
        self.entry_point.remove_trigger('hide')
        self.entry_point.add_trigger('show')

    def _refresh_tray_file(
        self, index: int, loaded_data: phile.notify.File,
        tracked_data: typing.List[phile.notify.File]
    ) -> None:
        if tracked_data:
            self.notify_tray_file.path.parent.mkdir(
                parents=True, exist_ok=True
            )
            self.notify_tray_file.save()
        else:
            self._remove_tray_file()

    def _remove_tray_file(self) -> None:
        self.notify_tray_file.path.unlink(missing_ok=True)


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    configuration = phile.configuration.Configuration()
    watching_observer = phile.watchdog_extras.Observer()
    watching_observer.start()
    asyncio.run(
        Monitor(
            configuration=configuration,
            watching_observer=watching_observer
        ).start()
    )
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
