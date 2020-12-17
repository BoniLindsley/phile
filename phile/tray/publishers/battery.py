#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import datetime
import functools
import pathlib
import psutil  # type: ignore[import]
import sys
import types
import typing

# External dependencies.
import watchdog.observers  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.tray
import phile.trigger
import phile.watchdog_extras


class File(phile.tray.File):

    def update(
        self, battery_state: typing.Optional[psutil._common.sbattery]
    ) -> None:
        raise NotImplementedError()


class PercentageFile(File):

    def update(
        self, battery_state: typing.Optional[psutil._common.sbattery]
    ) -> None:
        if battery_state is not None:
            percentage_text = f'{battery_state.percent:02.0f}'
        else:
            percentage_text = '-?'
        self.text_icon = f' B:{percentage_text}%'


class TimeFile(File):

    def update(
        self, battery_state: typing.Optional[psutil._common.sbattery]
    ) -> None:
        if battery_state is not None and battery_state.secsleft >= 0:
            timedelta = datetime.timedelta
            time_remaining = timedelta(seconds=battery_state.secsleft)
            hour, trailing = divmod(time_remaining, timedelta(hours=1))
            minute = trailing // timedelta(minutes=1)
            remaining_text = f'={hour}h{minute:02}'
        else:
            remaining_text = ''
        self.text_icon = f'{remaining_text}'


class _TrayFiles(contextlib.AbstractContextManager):
    """
    Responsible for managing tray files for battery.

    Use :meth:`update` to write a specific time into them.
    Use :meth:`unlink` to remove all the files.
    Use as a context manager to unlink them on close.
    """

    def __init__(
        self, *args, configuration: phile.configuration.Configuration,
        **kwargs
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        prefix = '70-phile-tray-battery-'
        self.files: typing.Tuple[File, ...] = (
            PercentageFile.from_path_stem(
                configuration=configuration,
                path_stem=prefix + '1-percentage'
            ),
            TimeFile.from_path_stem(
                configuration=configuration, path_stem=prefix + '2-time'
            ),
        )

    def __exit__(
        self, _exc_type: typing.Optional[typing.Type[BaseException]],
        _exc_value: typing.Optional[BaseException],
        _traceback: typing.Optional[types.TracebackType]
    ) -> typing.Optional[bool]:
        self.unlink()
        return None

    def unlink(self) -> None:
        for file in self.files:
            file.path.unlink(missing_ok=True)

    def update(self) -> None:
        battery_state = psutil.sensors_battery()
        for file in self.files:
            file.update(battery_state)
        for file in self.files:
            file.save()


@contextlib.contextmanager
def _prepare(
    configuration: phile.configuration.Configuration,
    watching_observer: watchdog.observers.Observer,
    trigger_directory: pathlib.Path
) -> typing.Iterator:
    with contextlib.ExitStack() as exit_stack:
        close_event = asyncio.Event()
        hide_event = asyncio.Event()
        show_event = asyncio.Event()
        entry_point = exit_stack.enter_context(
            phile.trigger.EntryPoint(
                callback_map={
                    'close': lambda _trigger_name: close_event.set(),
                    'hide': lambda _trigger_name: hide_event.set(),
                    'show': lambda _trigger_name: show_event.set(),
                },
                configuration=configuration,
                trigger_directory=trigger_directory,
            )
        )
        exit_stack.enter_context(
            phile.watchdog_extras.Scheduler(
                path_filter=entry_point.check_path,
                path_handler=functools.partial(
                    asyncio.get_running_loop().call_soon_threadsafe,
                    entry_point.activate_trigger
                ),
                watched_path=entry_point.trigger_directory,
                watching_observer=watching_observer,
            )
        )
        # Triggers have to be added after scheduling
        # so that their activations will be detected.
        entry_point.add_trigger('close')
        entry_point.add_trigger('hide')
        yield close_event, hide_event, show_event, entry_point


async def run(
    configuration: phile.configuration.Configuration,
    watching_observer: watchdog.observers.Observer,
    refresh_interval: datetime.timedelta = datetime.timedelta(seconds=5),
    trigger_directory: pathlib.
    Path = (pathlib.Path('phile-tray-battery'))
) -> None:
    with _prepare(
        configuration, watching_observer, trigger_directory
    ) as (close_event, hide_event, show_event, entry_point), _TrayFiles(
        configuration=configuration
    ) as tray_files:
        hide_task = asyncio.create_task(hide_event.wait())
        close_task = asyncio.create_task(close_event.wait())
        show_task = asyncio.create_task(show_event.wait())
        done_tasks: typing.Set[asyncio.Future] = set()
        while close_task not in done_tasks:
            timeout: typing.Optional[float]
            if show_task in done_tasks:
                await show_task
                show_event.clear()
                show_task = asyncio.create_task(show_event.wait())
                entry_point.remove_trigger('show')
                entry_point.add_trigger('hide')
            if hide_task in done_tasks:
                await hide_task
                hide_event.clear()
                hide_task = asyncio.create_task(hide_event.wait())
                entry_point.remove_trigger('hide')
                entry_point.add_trigger('show')
                tray_files.unlink()
                timeout = None
            else:
                tray_files.update()
                timeout = refresh_interval.total_seconds()
            done_tasks, _pending_tasks = await asyncio.wait(
                {close_task, hide_task, show_task},
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED
            )
        gather_task = asyncio.gather(
            close_task, hide_task, show_task, return_exceptions=True
        )
        gather_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await gather_task


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    configuration = phile.configuration.Configuration()
    watching_observer = phile.watchdog_extras.Observer()
    watching_observer.start()
    asyncio.run(
        run(
            configuration=configuration,
            watching_observer=watching_observer
        )
    )
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
