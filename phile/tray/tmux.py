#!/usr/bin/env python3
"""
--------------------------------------
Display tray files in tmux status line
--------------------------------------
"""

# Standard libraries.
import asyncio
import contextlib
import functools
import sys
import types
import typing

# External dependencies.
import watchdog.observers

# Internal packages.
import phile
import phile.asyncio
import phile.data
import phile.tmux
import phile.tmux.control_mode
import phile.tray
import phile.watchdog


class StatusRight:

    def __init__(
        self, *args: typing.Any,
        control_mode: phile.tmux.control_mode.Client,
        **kwargs: typing.Any
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._send_soon = control_mode.send_soon
        self._current_value = '\n'
        """Current status right string for tmux."""

    def __enter__(self) -> 'StatusRight':
        self.set('')
        return self

    def __exit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> typing.Optional[bool]:
        self._send_soon(
            phile.tmux.CommandBuilder.unset_global_status_right()
        )
        return None

    def set(self, value: str) -> None:
        if self._current_value != value:
            self._current_value = value
            self._send_soon(
                phile.tmux.CommandBuilder.set_global_status_right(value)
            )


def tray_files_to_tray_text(files: typing.List[phile.tray.File]) -> str:
    return ''.join(
        tray_file.text_icon for tray_file in files
        if tray_file.text_icon is not None
    )


async def run(
    *,
    configuration: phile.Configuration,
    control_mode: phile.tmux.control_mode.Client,
    watching_observer: watchdog.observers.api.BaseObserver,
) -> None:
    """Start updating ``status-right`` with tray file changes."""
    with contextlib.ExitStack() as stack:
        status_right = stack.enter_context(
            StatusRight(control_mode=control_mode)
        )
        sorter_handler: phile.data.UpdateCallback[phile.tray.File] = (
            lambda _index, _tray_file, tracked_data:
            (status_right.set(tray_files_to_tray_text(tracked_data)))
        )
        tray_sorter = phile.data.SortedLoadCache[phile.tray.File](
            create_file=phile.tray.File,
            on_insert=sorter_handler,
            on_pop=sorter_handler,
            on_set=sorter_handler,
        )
        stack.callback(tray_sorter.tracked_data.clear)
        # Start monitoring to not miss file events.
        stack.enter_context(
            phile.watchdog.Scheduler(
                path_filter=functools.partial(
                    phile.tray.File.check_path,
                    configuration=configuration
                ),
                path_handler=functools.partial(
                    asyncio.get_running_loop().call_soon_threadsafe,
                    tray_sorter.update,
                ),
                watched_path=configuration.tray_directory,
                watching_observer=watching_observer,
            )
        )
        # Update all existing tray files.
        tray_sorter.refresh(
            data_directory=configuration.tray_directory,
            data_file_suffix=configuration.tray_suffix
        )
        await control_mode.protocol.at_eof.wait()


async def read_byte(pipe: typing.Any) -> None:
    reader = asyncio.StreamReader()
    transport, protocol = (
        await asyncio.get_running_loop().connect_read_pipe(
            functools.partial(asyncio.StreamReaderProtocol, reader), pipe
        )
    )
    try:
        await reader.read(1)
    finally:
        transport.close()


async def async_main(argv: typing.List[str]) -> int:  # pragma: no cover
    async with phile.watchdog.observers.async_open(
    ) as watching_observer, phile.tmux.control_mode.open(
        control_mode_arguments=(phile.tmux.control_mode.Arguments())
    ) as control_mode, phile.asyncio.open_task(
        control_mode.run()
    ) as control_mode_task, phile.asyncio.open_task(
        run(
            configuration=phile.Configuration(),
            control_mode=control_mode,
            watching_observer=watching_observer,
        )
    ) as run_task, phile.asyncio.open_task(
        read_byte(sys.stdin)
    ) as stdin_task:
        done, pending = await asyncio.wait(
            (control_mode_task, run_task, stdin_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Try to reset status bar for a "graceful" exit.
        # Still does not read exit responses though.
        if done == {stdin_task}:
            control_mode.send_soon(
                phile.tmux.CommandBuilder.unset_global_status_right()
            )
            control_mode.send_soon(
                phile.tmux.CommandBuilder.exit_client()
            )
            done, pending = await asyncio.wait(
                (control_mode_task, run_task),
                return_when=asyncio.FIRST_COMPLETED,
            )
    return 0


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
