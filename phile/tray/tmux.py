#!/usr/bin/env python3
"""
-----------------------
Communicating with tmux
-----------------------

There is a control mode in tmux.
It allows communicating with the tmux server
using client ``stdin`` and ``stdout`` streams.
This avoids the need to start a new tmux process for each tmux command.
The :class:`ControlMode` class wraps basic communication needs
in control mode.
"""

# Standard libraries.
import asyncio
import contextlib
import dataclasses
import datetime
import functools
import io
import logging
import os
import pathlib
import pty
import select
import shlex
import signal
import subprocess
import sys
import types
import typing

# External dependencies.
import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]

# Internal packages.
from phile.configuration import Configuration
import phile.data
import phile.tray

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


class CommandBuilder:
    """
    Construct tmux command strings based on commands of interest.

    All construction methods are class methods
    since tmux state is not necessary.
    And if they are, they can be passed in from the parameters.
    The provided methods are added as necessary.
    They are not meant to be exhaustive.
    """

    @classmethod
    def exit_client(cls) -> str:
        """Let the server know the current client wants to exit."""
        return ''

    @classmethod
    def refresh_client(
        cls, *, no_output: typing.Optional[bool] = None
    ) -> str:
        """
        Send a client refresh request.

        :param no_output:
            If not :class:`None`,
            determines whether the tmux server
            should send ``%output`` messages.
            Otherwise, the current setting is left alone.
        :type no_output: :class:`bool` or :class:`None`
        """
        if no_output is None:
            flags = ''
        elif no_output:
            flags = ' -F no-output'
        else:
            flags = ' -F \'\''
        return '{command}{flags}'.format(
            command='refresh-client', flags=flags
        )

    @classmethod
    def set_destroy_unattached(cls, to_destroy: bool) -> str:
        """
        Set whether the current session exit when not attached.

        In particular, the session exits
        when the created subprocess is destroyed,
        or when it switches to a new session.

        It is not a good idea to use this on the control mode session,
        since iterating through session from a different client
        can cause the control mode session to become terminated.
        This can in turn crash the parent of the control mode process,
        and that is likely this Python interpreter,
        and then its parent which can be the tmux server
        if this script is launched from the tmux configuration script.
        """
        return 'set-option destroy-unattached {}'.format(
            'on' if to_destroy else 'off'
        )

    @classmethod
    def set_global_status_right(cls, new_status_string: str) -> str:
        """Change the tmux status line value to the given string."""
        return 'set-option -g status-right {}'.format(
            shlex.quote(new_status_string)
        )

    @classmethod
    def unset_global_status_right(cls) -> str:
        """Change the tmux status line value to the default."""
        return 'set-option -gu status-right'


def timedelta_to_seconds(
    timedelta: typing.Optional[datetime.timedelta] = None
) -> typing.Optional[float]:
    """Convert timedelta to seconds, preserving :data:`None`."""
    if timedelta is None:
        return None
    else:
        return timedelta.total_seconds()


def kill_server(
    *, timeout: typing.Optional[datetime.timedelta] = None
) -> None:
    """
    Sends a ``kill-server`` command to the default tmux server.

    :param timeout:
        Duration to wait for the command to return
        unless it is :data:`None`,
        in which case block until it returns.
    :type timeout: :class:`~datetime.timedelta` or :data:`None`
    """
    # Fetch tmux server information.
    _logger.debug('Kill server started.')
    pid_process = subprocess.run(
        args=['tmux', 'kill-server'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timedelta_to_seconds(timeout),
    )
    _logger.debug('Kill server completed.')
    _logger.debug('Kill server stdout: %s', pid_process.stdout)
    _logger.debug('Kill server stderr: %s', pid_process.stderr)


@dataclasses.dataclass
class ControlModeArguments:
    session_name: str = 'ctrl'
    tmux_configuration_path: typing.Optional[pathlib.Path] = None

    def to_list(self) -> typing.List[str]:
        """
        Returns a list of string arguments represented by ``self``.

        This is for use with :func:`~asyncio.create_subprocess_exec`.
        In particular, the returned list
        does not specify the program to be called.
        """
        arguments = ['-CC', '-u']
        """Command arguments for creating control mode client."""
        if self.tmux_configuration_path is not None:
            arguments.extend(('-f', str(self.tmux_configuration_path)))
        if self.session_name:
            arguments.extend((
                'new-session',
                '-A',
                '-s',
                self.session_name,
            ))
        return arguments


async def close_subprocess(
    subprocess: asyncio.subprocess.Process
) -> None:
    """Ensure the given subprocess is terminated."""
    # We do not know what state the process is in.
    # We assume the user had already exhausted
    # all nice ways to terminate it.
    # So just kill it.
    with contextlib.suppress(ProcessLookupError):
        subprocess.kill()
    # Killing just sends the request / signal.
    # Wait to make sure it is actually terminated.
    # And automatically-created pipes and inherited fds,
    # such as any given in stdin, stdout, stderr,
    # are closed after termination.
    await subprocess.communicate()


class ControlModeProtocol(asyncio.Protocol):

    class PrefixNotFound(RuntimeError):
        pass

    def __init__(self, *args, **kwargs):
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.received_data = asyncio.Queue()
        self.lines: typing.List[bytes] = []
        self.buffer = b''
        self.new_line_received = asyncio.Event()
        self.new_data_received = asyncio.Event()
        """
        Cleared or set depending on
        whether `buffer` is empty or not.
        """
        self.at_eof = asyncio.Event()
        self._next_line: typing.Optional[bytes] = None

    def data_received(self, data: bytes) -> None:
        newline = b'\r\n'
        separator = newline  # Loop entry condition
        while separator:
            content, separator, data = data.partition(newline)
            self.buffer += content + separator
            if separator:
                self.lines.append(self.buffer)
                self.buffer = b''
                self.new_line_received.set()
        self.new_data_received.set()

    def eof_received(self) -> bool:
        self.at_eof.set()
        return False

    async def peek_line(self) -> bytes:
        """
        Blocks forever if disconnected and drained.
        Up to the user to check :attr:`disconnected`.
        """
        with contextlib.suppress(IndexError):
            return self.lines[0]
        await self.new_line_received.wait()
        return self.lines[0]

    async def read_line(self) -> str:
        await self.peek_line()
        line = self.lines.pop(0).decode()
        if not self.lines:
            self.new_line_received.clear()
        return line

    async def remove_prefix(self, prefix: bytes) -> None:
        """New line ``\r\n`` is not allowed in ``prefix``."""
        # TODO[Python 3.9]: Use `str.removeprefix`.
        assert prefix.find(b'\r\n') == -1
        found = False
        prefix_length = len(prefix)
        try:
            while not found:
                await self.new_data_received.wait()
                if self.lines:
                    line = await self.peek_line()
                    if line[0:prefix_length] != prefix:
                        raise ControlModeProtocol.PrefixNotFound()
                    self.lines[0] = line[len(prefix):]
                    found = True
                else:
                    if len(self.buffer) >= prefix_length:
                        if self.buffer[0:prefix_length] != prefix:
                            raise ControlModeProtocol.PrefixNotFound()
                        self.buffer = self.buffer[len(prefix):]
                        if not self.buffer:
                            self.new_data_received.clear()
                        found = True
                    elif self.buffer != prefix[0:len(self.buffer)]:
                        raise ControlModeProtocol.PrefixNotFound()
                    # Breaks invariant of having data but cleared event.
                    # This is needed to detect incoming data.
                    # This is restored in the next iteration
                    # when data arrives.
                    self.new_data_received.clear()
        finally:
            # Restore invariant of event.
            if self.buffer:
                self.new_data_received.set()
            else:
                self.new_data_received.clear()

    async def drop_lines_until_starts_with(
        self,
        prefix: typing.Union[str, typing.Tuple[str, ...]],
    ) -> str:
        next_line = await self.read_line()
        while not next_line.startswith(prefix):
            next_line = await self.read_line()
        return next_line

    async def drop_lines_not_starting_with(
        self,
        prefix: typing.Union[str, typing.Tuple[str, ...]],
    ) -> str:
        line = await self.drop_lines_until_starts_with(prefix)
        self.lines.insert(0, line.encode())
        return line

    async def read_lines_until_starts_with(
        self,
        prefix: typing.Union[str, typing.Tuple[str, ...]],
    ) -> typing.List[str]:
        next_line = await self.read_line()
        lines = [next_line]
        while not next_line.startswith(prefix):
            next_line = await self.read_line()
            lines.append(next_line)
        return lines

    async def read_block(self) -> typing.List[str]:
        begin_line = await self.drop_lines_until_starts_with('%begin ')
        content_lines = await self.read_lines_until_starts_with(
            ('%end ', '%error ')
        )
        content_lines.insert(0, begin_line)
        return content_lines


@dataclasses.dataclass
class ControlMode:

    transport: asyncio.WriteTransport
    protocol: ControlModeProtocol
    subprocess: asyncio.subprocess.Process

    def __post_init__(self) -> None:
        self._commands: asyncio.Queue[str] = asyncio.Queue()

    def send_soon(self, command: str) -> None:
        # Cannot await on a put directly here.
        # The tmux client is not allowed to send commands
        # in the middle of a response block,
        # so that needs to be synchronised.
        self._commands.put_nowait(command)

    async def run_message_loop(self) -> None:
        await self.protocol.remove_prefix(b'\x1bP' b'1000p')
        command = 'NotCommand-EnterLoop'
        # Exit command is an empty line.
        while command:
            # The server sends one block at the beginniing.
            await self.protocol.read_block()
            with contextlib.ExitStack() as stack:
                exit_task = asyncio.create_task(
                    self.protocol.drop_lines_not_starting_with('%exit')
                )
                stack.callback(exit_task.cancel)
                command_task = asyncio.create_task(self._commands.get())
                stack.callback(command_task.cancel)
                done, pending = await asyncio.wait(
                    (exit_task, command_task),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if exit_task in done:
                    break
                command = await command_task
            self._commands.task_done()
            self.transport.write(command.encode() + b'\n')
        # This is for graceful shutdown. Not really needed.
        # Left here for documentation purposes on shutdown responses.
        if False:  # pragma: no cover
            exit_response = '%exit\r\n' '\x1b\\'
            await self.protocol.drop_lines_until_starts_with(
                exit_response
            )
            await self.protocol.remove_prefix(exit_response.encode())

    async def run(self) -> None:
        with contextlib.ExitStack() as stack:
            message_task = asyncio.create_task(self.run_message_loop())
            stack.callback(message_task.cancel)
            eof_task = asyncio.create_task(self.protocol.at_eof.wait())
            stack.callback(eof_task.cancel)
            terminate_task = asyncio.create_task(self.subprocess.wait())
            stack.callback(terminate_task.cancel)
            await asyncio.wait(
                (message_task, eof_task, terminate_task),
                return_when=asyncio.FIRST_COMPLETED,
            )


@contextlib.asynccontextmanager
async def open_control_mode(
    control_mode_arguments: ControlModeArguments
) -> typing.AsyncIterator:
    async with contextlib.AsyncExitStack() as stack:
        tty_fd, subprocess_tty_fd = pty.openpty()
        stack.callback(os.close, tty_fd)
        # Close the other fd immediately after giving it to subprocess.
        # It is not used by us.
        try:
            # Since stdout is parsed, stderr has to be sent elsewhere.
            subprocess = await asyncio.create_subprocess_exec(
                'tmux',
                *control_mode_arguments.to_list(),
                stdin=subprocess_tty_fd,
                stdout=subprocess_tty_fd,
                stderr=asyncio.subprocess.PIPE,
            )
            stack.push_async_callback(close_subprocess, subprocess)
        finally:
            os.close(subprocess_tty_fd)
        loop = asyncio.get_running_loop()
        transport: asyncio.WriteTransport
        transport, _ = (  # Variable type
            await loop.connect_write_pipe(  # type: ignore[assignment]
                asyncio.Protocol,
                open(tty_fd, buffering=0, mode='wb', closefd=False),
            )
        )
        stack.callback(transport.close)
        protocol: ControlModeProtocol
        read_transport, protocol = (  # Variable type.
            await loop.connect_read_pipe(  # type: ignore[assignment]
                ControlModeProtocol,
                open(tty_fd, buffering=0, mode='rb', closefd=False),
            )
        )
        stack.callback(read_transport.close)
        yield ControlMode(
            transport=transport,
            protocol=protocol,
            subprocess=subprocess
        )


class StatusRight:

    def __init__(
        self, *args, control_mode: ControlMode, **kwargs
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
        self._send_soon(CommandBuilder.unset_global_status_right())
        return None

    def set(self, value: str) -> None:
        if self._current_value != value:
            self._current_value = value
            self._send_soon(
                CommandBuilder.set_global_status_right(value)
            )


def tray_files_to_tray_text(files: typing.List[phile.tray.File]) -> str:
    return ''.join(
        tray_file.text_icon for tray_file in files
        if tray_file.text_icon is not None
    )


async def run(
    *,
    configuration: Configuration,
    control_mode: ControlMode,
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
            phile.watchdog_extras.Scheduler(
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


async def read_byte(pipe) -> None:
    reader = asyncio.StreamReader()
    _, protocol = await asyncio.get_running_loop().connect_read_pipe(
        functools.partial(asyncio.StreamReaderProtocol, reader), pipe
    )
    await reader.read(1)


async def async_main(argv: typing.List[str]) -> int:  # pragma: no cover
    async with contextlib.AsyncExitStack() as stack:
        watching_observer = watchdog.observers.Observer()
        watching_observer.start()
        stack.callback(watching_observer.stop)
        control_mode = await stack.enter_async_context(
            open_control_mode(
                control_mode_arguments=ControlModeArguments()
            )
        )
        control_mode_task = asyncio.create_task(control_mode.run())
        stack.callback(control_mode_task.cancel)
        run_task = asyncio.create_task(
            run(
                configuration=Configuration(),
                control_mode=control_mode,
                watching_observer=watching_observer,
            )
        )
        stack.callback(run_task.cancel)
        stdin_task = asyncio.create_task(read_byte(sys.stdin))
        stack.callback(stdin_task.cancel)
        done, pending = await asyncio.wait(
            (control_mode_task, run_task, stdin_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Try to reset status bar for a "graceful" exit.
        # Still does not read exit responses though.
        if done == {stdin_task}:
            control_mode.send_soon(
                CommandBuilder.unset_global_status_right()
            )
            control_mode.send_soon(CommandBuilder.exit_client())
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
