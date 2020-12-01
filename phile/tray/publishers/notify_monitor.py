#!/usr/bin/env python3

# Standard library.
import asyncio
import bisect
import contextlib
import dataclasses
import json
import logging
import pathlib
import signal
import socket
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


@dataclasses.dataclass
class Converter:  # pragma: no cover
    """Convert a notify file event to a notify file."""

    configuration: phile.configuration.Configuration
    paths_handler: phile.watchdog_extras.PathsHandler
    """Callback repsonsible of processing notify files by path."""

    def __call__(
        self, watchdog_event: watchdog.events.FileSystemEvent
    ) -> None:
        """
        Calls :data:`notify_handler` with the notify file paths
        given in the ``watchdog_event``.
        """
        self.paths_handler(
            path for path in
            phile.watchdog_extras.to_file_paths(watchdog_event)
            if phile.notify.File.check_path(
                configuration=self.configuration,
                path=path,
            )
        )


def create_notify_scheduler(
    configuration: phile.configuration.Configuration,
    paths_handler: phile.watchdog_extras.PathsHandler,
    watching_observer: watchdog.observers.Observer,
) -> phile.watchdog_extras.Scheduler:
    # Turn file system events into notify files for processing.
    event_converter = Converter(
        paths_handler=paths_handler,
        configuration=configuration,
    )
    # Use a scheduler to toggle the event handling on and off.
    dispatcher = phile.watchdog_extras.Dispatcher(
        event_handler=event_converter
    )
    watched_path = configuration.notification_directory
    watched_path.mkdir(exist_ok=True, parents=True)
    return phile.watchdog_extras.Scheduler(
        watchdog_handler=dispatcher,
        watched_path=watched_path,
        watching_observer=watching_observer,
    )


def create_trigger_scheduler(
    configuration: phile.configuration.Configuration,
    entry_point: phile.trigger.EntryPoint,
    trigger_handler: typing.Callable[[str], None],
    watching_observer: watchdog.observers.Observer,
) -> phile.watchdog_extras.Scheduler:
    # Turn file system events into trigger names to process.
    event_converter = phile.trigger.EventConverter(
        configuration=configuration,
        trigger_handler=trigger_handler,
    )
    # Filter out non-trigger activation events.
    event_filter = phile.trigger.EventFilter(
        configuration=configuration,
        event_handler=event_converter,
        trigger_directory=entry_point.trigger_directory,
    )
    # Use a scheduler to toggle the event handling on and off.
    dispatcher = phile.watchdog_extras.Dispatcher(
        event_handler=event_filter
    )
    return phile.watchdog_extras.Scheduler(
        watchdog_handler=dispatcher,
        watched_path=entry_point.trigger_directory,
        watching_observer=watching_observer,
    )


class TriggerSwitch:  # pragma: no cover

    def __init__(self, *args, **kwargs) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.callback_map: typing.Dict[str, phile.trigger.Handler] = {}
        """
        Callbacks to forward to.

        Not threadsafe.
        In particular, this should not be modified
        while ``self`` is set as a callback in a different thread.
        """

    def __call__(self, trigger_name: str) -> None:
        callback_to_forward_to = self.callback_map.get(
            trigger_name, self.unimplemented_trigger
        )
        callback_to_forward_to(trigger_name)

    def unimplemented_trigger(self, trigger_name: str) -> None:
        _logger.warning('Unknown trigger command: %s', trigger_name)


class DefaultTrayFile(phile.tray.File):

    def __init__(
        self,
        *args,
        configuration: phile.configuration.Configuration,
        name: str = '30-phile-notify-tray',
        text_icon='N',
        **kwargs
    ):
        super().__init__(
            *args, configuration=configuration, name=name, **kwargs
        )
        self.text_icon = text_icon


def load_file(path: pathlib.Path) -> phile.notify.File:
    file = phile.notify.File(path=path)
    with contextlib.suppress(FileNotFoundError, IsADirectoryError):
        file.load()
    return file


class Monitor:

    def __init__(
        self, *args, configuration: phile.configuration.Configuration,
        watching_observer: watchdog.observers.Observer, **kwargs
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]

        self._configuration = configuration
        self.notify_tray_file = DefaultTrayFile(
            configuration=configuration
        )
        """Read-only."""
        self._watching_observer = watching_observer

        self.entry_point = phile.trigger.EntryPoint(
            configuration=configuration,
            trigger_directory=pathlib.Path('phile-notify-tray'),
        )
        self.trigger_switch = TriggerSwitch()
        self.notify_sorter = phile.data.SortedLoadCache(
            load=load_file,
            on_insert=self._refresh_tray_file,
            on_pop=self._refresh_tray_file,
        )

    async def start(self) -> None:
        running_loop = asyncio.get_running_loop()
        call_soon_threadsafe = running_loop.call_soon_threadsafe
        self.trigger_scheduler = create_trigger_scheduler(
            configuration=self._configuration,
            entry_point=self.entry_point,
            trigger_handler=(
                # Handler must return None.
                # To be refactored later.
                lambda trigger_name: (
                    None if call_soon_threadsafe(
                        self.trigger_switch, trigger_name
                    ) else None
                )
            ),
            watching_observer=self._watching_observer
        )
        self.notify_scheduler = create_notify_scheduler(
            configuration=self._configuration,
            paths_handler=(
                lambda paths: (
                    None if call_soon_threadsafe(
                        self.notify_sorter.update_paths, paths
                    ) else None
                )
            ),
            watching_observer=self._watching_observer
        )
        with contextlib.ExitStack() as exit_stack:
            exit_stack.callback(self.entry_point.unbind)
            self.entry_point.bind()
            self.entry_point.add_trigger('close')
            close_event = asyncio.Event()
            self.trigger_switch.callback_map.update(
                close=lambda trigger_name: close_event.set()
            )
            exit_stack.callback(self.trigger_scheduler.unschedule)
            self.trigger_scheduler.schedule()
            exit_stack.callback(self._hide)
            self._show()
            await close_event.wait()

    def _show(self, *args, **kwargs) -> None:
        self.notify_scheduler.schedule()
        self.notify_sorter.refresh(
            data_directory=self._configuration.notification_directory,
            data_file_suffix=self._configuration.notification_suffix
        )
        self.entry_point.remove_trigger('show')
        self.entry_point.add_trigger('hide')

    def _hide(self, *args, **kwargs) -> None:
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
        self.notify_tray_file.remove()


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
