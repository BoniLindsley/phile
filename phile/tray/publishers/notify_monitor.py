#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import functools
import logging
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

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


class TriggerSwitch:  # pragma: no cover

    def __init__(self, *args, **kwargs) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.callback_map: typing.Dict[str, phile.trigger.Handler] = {}

    def __call__(self, trigger_name: str) -> None:
        callback_to_forward_to = self.callback_map.get(
            trigger_name, self.unimplemented_trigger
        )
        callback_to_forward_to(trigger_name)

    def unimplemented_trigger(self, trigger_name: str) -> None:
        _logger.warning('Unknown trigger command: %s', trigger_name)


class Monitor:

    def __init__(
        self, *args, configuration: phile.configuration.Configuration,
        watching_observer: watchdog.observers.Observer, **kwargs
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]

        self._configuration = configuration
        self.notify_tray_file = phile.tray.File.from_path_stem(
            configuration=configuration,
            path_stem='30-phile-notify-tray',
            text_icon='N'
        )
        """Read-only."""
        self._watching_observer = watching_observer
        self.entry_point = phile.trigger.EntryPoint(
            configuration=configuration,
            trigger_directory=pathlib.Path('phile-notify-tray'),
        )
        self.trigger_switch = TriggerSwitch()
        self.notify_sorter = (
            phile.data.SortedLoadCache[phile.notify.File](
                create_file=phile.notify.File,
                on_insert=self._refresh_tray_file,
                on_pop=self._refresh_tray_file,
            )
        )

    async def start(self) -> None:
        configuration = self._configuration
        watching_observer = self._watching_observer
        running_loop = asyncio.get_running_loop()
        call_soon_threadsafe = running_loop.call_soon_threadsafe
        self.trigger_scheduler = phile.watchdog_extras.Scheduler(
            path_filter=(
                lambda path: path.suffix == configuration.trigger_suffix
            ),
            path_handler=lambda path: (
                call_soon_threadsafe(self.trigger_switch, path.stem)
                if not path.is_file() else None
            ),
            watched_path=self.entry_point.trigger_directory,
            watching_observer=watching_observer,
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
        with contextlib.ExitStack() as exit_stack:
            exit_stack.callback(self.entry_point.unbind)
            self.entry_point.bind()
            self.entry_point.add_trigger('close')
            close_event = asyncio.Event()
            exit_stack.callback(self.trigger_switch.callback_map.clear)
            self.trigger_switch.callback_map.update(
                close=lambda trigger_name: close_event.set(),
                hide=lambda trigger_name: self._hide(),
                show=lambda trigger_name: self._show(),
            )
            exit_stack.callback(self.trigger_scheduler.unschedule)
            self.trigger_scheduler.schedule()
            exit_stack.callback(self._hide)
            self._show()
            await close_event.wait()

    def _show(self) -> None:
        configuration = self._configuration
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
