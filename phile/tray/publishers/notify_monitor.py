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
    notify_handler: phile.notify.FileHandler
    """Callback repsonsible of processing notify by name"""

    def __call__(
        self, watchdog_event: watchdog.events.FileSystemEvent
    ) -> None:
        """
        Calls :data:`notify_handler` with the notify file
        given in the ``watchdog_event``.
        """
        notifications = [
            phile.notify.File(path=path) for path in
            phile.watchdog_extras.to_file_paths(watchdog_event)
            if phile.notify.File.check_path(
                configuration=self.configuration,
                path=path,
            )
        ]
        for notification in notifications:
            self.notify_handler(notification)


class Sorter:  # pragma: no cover
    """
    Collect notify files into a list.

    Not threadsafe.
    In particular, its callback members should not be modified
    while ``self`` is set as a callback in a different thread.
    """

    def __init__(
        self,
        *args,
        configuration: phile.configuration.Configuration,
        **kwargs,
    ) -> None:
        """
        :param ~phile.configuration.Configuration configuration:
            Information on what constitute a notify file.
        """
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._configuration = configuration
        """Determines where and which files are notify files."""
        self.notify_files: typing.List[phile.notify.File] = []
        """Keeps track of known notify files."""
        self.insert = self._noop_handler
        """
        Called when an untracked notify file is found.

        It is given the index at which the notify file is inserted at.
        """
        self.pop = self._noop_handler
        """
        Called when a tracked notify file is deleted.

        It is given the index the notify file was at before removal.
        """
        self.set_item = self._noop_handler
        """
        Called when a tracked notify file is modified.

        It is given the index the notify file is at.
        """

    def __call__(self, notify_file: phile.notify.File) -> None:
        """
        Forwards to handlers
        depending on how :data:`notify_files` is changed.
        Call different handlers depending on the given ``notify_file``.

        :param ~phile.notify.File notify_file:
            The notify file to insert or update in `:data:`notify_files`
            if it exists,
            or to pop from it otherwise.

        Tracking of the given ``notify_file`` in  :data:`notify_files`
        is updated before the handlers are called.
        """

        index = bisect.bisect_left(self.notify_files, notify_file)
        is_tracked: bool
        try:
            is_tracked = self.notify_files[index] == notify_file
        except IndexError:
            is_tracked = False

        notify_file_exists: bool
        try:
            notify_text = notify_file.read()
        except FileNotFoundError:
            notify_file_exists = False
        except json.decoder.JSONDecodeError:
            notify_file_exists = False
            _logger.warning(
                'Tray file decoding failed: {}'.format(notify_file.path)
            )
        else:
            notify_file_exists = True

        if not notify_file_exists:
            if is_tracked:
                self.notify_files.pop(index)
                self.pop(index, notify_file)
        elif is_tracked:
            self.notify_files[index] = notify_file
            self.set_item(index, notify_file)
        else:
            self.notify_files.insert(index, notify_file)
            self.insert(index, notify_file)

    def load_all(self):
        assert len(self.notify_files) == 0
        # Update all existing notify files.
        configuration = self._configuration
        for notify_file_path in configuration.notification_directory.glob(
            '*' + self._configuration.notification_suffix
        ):
            if not notify_file_path.is_file():
                continue
            notify_file = phile.notify.File(path=notify_file_path)
            self.__call__(notify_file)

    def _noop_handler(self, index: int, notify_file: phile.notify.File):
        """Implementation detail."""
        pass


def create_notify_scheduler(
    configuration: phile.configuration.Configuration,
    notify_handler: typing.Callable[[phile.notify.File], None],
    watching_observer: watchdog.observers.Observer,
) -> phile.watchdog_extras.Scheduler:
    # Turn file system events into notify files for processing.
    event_converter = Converter(
        notify_handler=notify_handler,
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
        self.notify_sorter = Sorter(configuration=configuration)
        self.notify_sorter.insert = self._refresh_tray_file
        self.notify_sorter.pop = self._refresh_tray_file

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
            notify_handler=(
                lambda notify_file: (
                    None if call_soon_threadsafe(
                        self.notify_sorter, notify_file
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
        self.notify_sorter.load_all()
        self.entry_point.remove_trigger('show')
        self.entry_point.add_trigger('hide')

    def _hide(self, *args, **kwargs) -> None:
        self.notify_scheduler.unschedule()
        self.notify_sorter.notify_files.clear()
        self._refresh_tray_file()
        self.entry_point.remove_trigger('hide')
        self.entry_point.add_trigger('show')

    def _refresh_tray_file(self, *args, **kwargs) -> None:
        if self.notify_sorter.notify_files:
            self.notify_tray_file.path.parent.mkdir(
                parents=True, exist_ok=True
            )
            self.notify_tray_file.save()
        else:
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
