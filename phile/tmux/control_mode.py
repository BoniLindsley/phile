#!/usr/bin/env python3
"""
There is a control mode in tmux.
It allows communicating with the tmux server
using client ``stdin`` and ``stdout`` streams.
This avoids the need to start a new tmux process for each tmux command.
The module wraps basic communication needs in control mode.
"""

# Standard libraries.
import asyncio
import builtins
import contextlib
import dataclasses
import os
import pathlib
import pty
import typing

# Internal packages.
import phile.asyncio


@dataclasses.dataclass
class Arguments:
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


class Protocol(asyncio.Protocol):

    class PrefixNotFound(RuntimeError):
        pass

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
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
        assert prefix.find(b'\r\n') == -1
        found = False
        prefix_length = len(prefix)
        try:
            while not found:
                await self.new_data_received.wait()
                if self.lines:
                    line = await self.peek_line()
                    if line[0:prefix_length] != prefix:
                        raise Protocol.PrefixNotFound()
                    self.lines[0] = line[len(prefix):]
                    found = True
                else:
                    if len(self.buffer) >= prefix_length:
                        result = self.buffer.removeprefix(prefix)
                        if result is self.buffer:
                            raise Protocol.PrefixNotFound()
                        self.buffer = result
                        if not result:
                            self.new_data_received.clear()
                        found = True
                    elif self.buffer != prefix[0:len(self.buffer)]:
                        raise Protocol.PrefixNotFound()
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
class Client:

    transport: asyncio.WriteTransport
    protocol: Protocol
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
            # TODO[python/mypy#9922]: Remove type declaration.
            command_task: asyncio.Task[str]
            async with phile.asyncio.open_task(
                self.protocol.drop_lines_not_starting_with('%exit'),
                suppress_cancelled_error_if_not_done=True,
            ) as exit_task, phile.asyncio.open_task(
                self._commands.get(),
                suppress_cancelled_error_if_not_done=True,
            ) as command_task:
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
        async with phile.asyncio.open_task(
            self.run_message_loop(),
            suppress_cancelled_error_if_not_done=True,
        ) as message_task, phile.asyncio.open_task(
            self.protocol.at_eof.wait(),
            suppress_cancelled_error_if_not_done=True,
        ) as eof_task, phile.asyncio.open_task(
            self.subprocess.wait(),
            suppress_cancelled_error_if_not_done=True,
        ) as terminate_task:
            await asyncio.wait(
                (message_task, eof_task, terminate_task),
                return_when=asyncio.FIRST_COMPLETED,
            )


@contextlib.asynccontextmanager
async def open(
    control_mode_arguments: Arguments
) -> typing.AsyncIterator[Client]:
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
            stack.push_async_callback(
                phile.asyncio.close_subprocess, subprocess
            )
        finally:
            os.close(subprocess_tty_fd)
        loop = asyncio.get_running_loop()
        transport: asyncio.WriteTransport
        transport, _ = (  # Variable type.
            await loop.connect_write_pipe(  # type: ignore[assignment]
                asyncio.Protocol,
                builtins.open(
                    tty_fd, buffering=0, mode='wb', closefd=False
                ),
            )
        )
        stack.callback(transport.close)
        protocol: Protocol
        read_transport, protocol = (  # Variable type.
            await loop.connect_read_pipe(  # type: ignore[assignment]
                Protocol,
                builtins.open(
                    tty_fd, buffering=0, mode='rb', closefd=False
                ),
            )
        )
        stack.callback(read_transport.close)
        yield Client(
            transport=transport,
            protocol=protocol,
            subprocess=subprocess
        )
