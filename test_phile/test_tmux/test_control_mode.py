#!/usr/bin/env python3
"""
-----------------------------------
Test :mod:`phile.tmux.control_mode`
-----------------------------------
"""

# Standard library.
import asyncio
import contextlib
import pathlib
import socket
import typing
import unittest
import unittest.mock

# Internal packages.
import phile.asyncio
import phile.tmux
import phile.tmux.control_mode
from .test_init import UsesTmux


class TestArguments(unittest.TestCase):
    """Tests :class:`~phile.tmux.control_mode.Arguments`."""

    def test_default(self) -> None:
        """Default joins ``ctrl`` session with no configuration."""
        arguments = phile.tmux.control_mode.Arguments()
        self.assertEqual(
            arguments.to_list(),
            ['-CC', '-u', 'new-session', '-A', '-s', 'ctrl']
        )

    def test_no_session(self) -> None:
        """Session name can be removed to create a new session."""
        arguments = phile.tmux.control_mode.Arguments(session_name='')
        self.assertEqual(arguments.to_list(), ['-CC', '-u'])

    def test_custom_configuration(self) -> None:
        """Server configuration can be changed."""
        arguments = phile.tmux.control_mode.Arguments(
            tmux_configuration_path=pathlib.Path('conf')
        )
        self.assertEqual(
            arguments.to_list(), [
                '-CC', '-u', '-f', 'conf', 'new-session', '-A', '-s',
                'ctrl'
            ]
        )


class TestProtocol(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.tmux.control_mode.Protocol`."""

    async def asyncSetUp(self) -> None:
        loop = asyncio.get_running_loop()
        reader, self.sender = socket.socketpair()
        self.addCleanup(reader.close)
        self.addCleanup(self.sender.close)
        self.protocol: phile.tmux.control_mode.Protocol
        transport, self.protocol = (
            await loop.connect_read_pipe(  # type: ignore[assignment]
                phile.tmux.control_mode.Protocol, reader
            )
        )
        self.addCleanup(transport.close)

    async def test_data_received(self) -> None:
        """New lines are detected as data are received."""
        self.sender.send(b'\r\n')
        await phile.asyncio.wait_for(
            self.protocol.new_data_received.wait()
        )

    async def test_peek_line(self) -> None:
        """Can check a line which tmux says ends with ``\\r\\n``."""
        self.sender.send(b'line-1\n\r\n\r')
        line = await phile.asyncio.wait_for(self.protocol.peek_line())
        self.assertEqual(line, b'line-1\n\r\n')
        line = await phile.asyncio.wait_for(self.protocol.peek_line())
        self.assertEqual(line, b'line-1\n\r\n')

    async def test_read_line(self) -> None:
        """Can read a line which tmux defines as ending with ``\r\n``."""
        self.sender.send(b'line-1\n\r\n\r')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, 'line-1\n\r\n')

    async def test_read_line_with_two_lines(self) -> None:
        """Can read each line separately even if received together."""
        self.sender.send(b'line-1\n\r\n\nline-2\r\n')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, 'line-1\n\r\n')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '\nline-2\r\n')

    async def test_read_line_merges_trailing_lines(self) -> None:
        """Can read a line that was broken up when sending."""
        self.sender.send(b'line-1\n\r')
        self.sender.send(b'\n\nline-2')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, 'line-1\n\r\n')

    async def test_remove_prefix_after_reading_line(self) -> None:
        """Remove prefix from the first line."""
        self.sender.send(b'\x1bP1000p%begin\r\n')
        prefix = b'\x1bP1000p'
        await phile.asyncio.wait_for(self.protocol.remove_prefix(prefix))
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_remove_prefix_without_new_line(self) -> None:
        self.sender.send(b'\x1b\\')
        prefix = b'\x1b\\'
        await phile.asyncio.wait_for(self.protocol.remove_prefix(prefix))
        self.sender.send(b'%begin\r\n')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_remove_prefix_without_new_line_or_drain(self) -> None:
        self.sender.send(b'\x1b\\%be')
        prefix = b'\x1b\\'
        await phile.asyncio.wait_for(self.protocol.remove_prefix(prefix))
        self.sender.send(b'gin\r\n')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_remove_prefix_loops_if_buffer_too_short(self) -> None:
        self.sender.send(b'%beg')
        prefix = b'%begin'
        remove_task = asyncio.create_task(
            self.protocol.remove_prefix(prefix)
        )
        # This ensures one iteration of the loop
        # in the `remove_prefix` coroutine is queued to be run.
        # So the wait below for the coroutine to finish
        # happens after that iteration.
        # This ensures the loop in the coroutine
        # has to go into a second iteration,
        # and the coroutine check sent data as a whole
        # even if sent separately.
        await phile.asyncio.wait_for(
            self.protocol.new_data_received.wait()
        )
        self.sender.send(b'in')
        await phile.asyncio.wait_for(remove_task)
        self.sender.send(b'%end\r\n')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '%end\r\n')

    async def test_remove_prefix_raises_if_not_found_in_line(
        self
    ) -> None:
        self.sender.send(b'%begin\r\n')
        prefix = b'\x1bP1000p'
        with self.assertRaises(
            phile.tmux.control_mode.Protocol.PrefixNotFound
        ):
            await phile.asyncio.wait_for(
                self.protocol.remove_prefix(prefix)
            )
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_remove_prefix_raises_if_not_found_in_buffer(
        self
    ) -> None:
        self.sender.send(b'%begin')
        prefix = b'no'
        with self.assertRaises(
            phile.tmux.control_mode.Protocol.PrefixNotFound
        ):
            await phile.asyncio.wait_for(
                self.protocol.remove_prefix(prefix)
            )
        self.sender.send(b'\r\n')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_remove_prefix_raises_early_if_different(self) -> None:
        self.sender.send(b'%')
        prefix = b'\x1b\\'
        with self.assertRaises(
            phile.tmux.control_mode.Protocol.PrefixNotFound
        ):
            await phile.asyncio.wait_for(
                self.protocol.remove_prefix(prefix)
            )
        self.sender.send(b'begin\r\n')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_drop_lines_until_starts_with(self) -> None:
        self.sender.send(b'line-1\n\r\n%beginner\r\n%endder\r\n')
        line = await phile.asyncio.wait_for(
            self.protocol.drop_lines_until_starts_with('%begin')
        )
        self.assertEqual(line, '%beginner\r\n')
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '%endder\r\n')

    async def test_read_lines_until_starts_with(self) -> None:
        """Record lines until a specifix prefix is found."""
        self.sender.send(b'line-1\n\r\n%beginner\r\n%endder\r\n')
        lines = await phile.asyncio.wait_for(
            self.protocol.read_lines_until_starts_with('%begin')
        )
        self.assertEqual(lines, ['line-1\n\r\n', '%beginner\r\n'])
        line = await phile.asyncio.wait_for(self.protocol.read_line())
        self.assertEqual(line, '%endder\r\n')

    async def test_read_block(self) -> None:
        """Reading a block between ``%begin`` and ``%end``."""
        self.sender.send(b'line-1\n\r\n%begin er\r\n%end er\r\n')
        content = await phile.asyncio.wait_for(
            self.protocol.read_block()
        )
        self.assertEqual(content, ['%begin er\r\n', '%end er\r\n'])


class UsesClientWithFakeSubprocess(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        """Create sockets to send fake tmux messages."""
        await super().asyncSetUp()
        # Communication between fake server and fake subprocess.
        server_socket, client_socket = socket.socketpair()
        self.addCleanup(server_socket.close)
        self.addCleanup(client_socket.close)
        self.server = server_socket
        server_socket.setblocking(False)
        self.server_sendall: typing.Callable[[bytes], typing.Any] = (
            lambda data: asyncio.
            create_task(loop.sock_sendall(server_socket, data))
        )
        # Communication between fake subprocess and client.
        loop = asyncio.get_running_loop()
        transport: asyncio.WriteTransport
        protocol: phile.tmux.control_mode.Protocol
        transport, protocol = (
            await loop.create_connection(  # type: ignore[assignment]
                phile.tmux.control_mode.Protocol, sock=client_socket
            )
        )
        self.addCleanup(transport.close)
        self.subprocess = subprocess = unittest.mock.Mock()
        subprocess_stopped = asyncio.Event()
        subprocess.kill = subprocess_stopped.set
        subprocess.terminate = subprocess_stopped.set
        subprocess.wait = subprocess_stopped.wait
        self.client = phile.tmux.control_mode.Client(
            transport=transport,
            protocol=protocol,
            subprocess=subprocess
        )

    async def check_server_recieves(self, command: str) -> None:
        expected_data = command.encode() + b'\n'
        data = await phile.asyncio.wait_for(
            asyncio.get_running_loop().sock_recv(
                self.server, len(expected_data)
            )
        )
        self.assertEqual(expected_data, data)
        await self.server_sendall(b'%begin 1\r\n%end 1\r\n')

    async def check_status_right_set_to(self, tray_text: str) -> None:
        command = phile.tmux.CommandBuilder.set_global_status_right(
            tray_text
        )
        await self.check_server_recieves(command)


class TestClient(
    UsesClientWithFakeSubprocess, unittest.IsolatedAsyncioTestCase
):
    """Tests :func:`~phile.tmux.control_mode.Client`."""

    async def test_run_returns_on_immediate_disconnect(self) -> None:
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        self.server.close()
        await phile.asyncio.wait_for(run_task)

    async def test_run_returns_on_disconnect_after_startup(self) -> None:
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')
        self.server.close()
        await phile.asyncio.wait_for(run_task)

    async def test_send_soon_does_send_eventually(self) -> None:
        loop = asyncio.get_running_loop()
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')
        self.client.send_soon(phile.tmux.CommandBuilder.exit_client())
        line = await phile.asyncio.wait_for(
            loop.sock_recv(self.server, 1)
        )
        self.assertEqual(line, b'\n')

    async def test_run_can_terminate_to_exit_response(self) -> None:
        loop = asyncio.get_running_loop()
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')
        await self.server_sendall(b'%exit\r\n\x1b\\')
        await phile.asyncio.wait_for(run_task)

    async def test_run_can_terminate_to_a_disconnect(self) -> None:
        loop = asyncio.get_running_loop()
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        self.server.close()
        await phile.asyncio.wait_for(run_task)


class TestOpen(UsesTmux, unittest.IsolatedAsyncioTestCase):
    """
    Tests :func:`~phile.tmux.control_mode.open`.

    Integration test on whether ``tmux`` can be communicated with.
    """

    async def asyncSetUp(self) -> None:
        self.stack = stack = contextlib.AsyncExitStack()
        self.addAsyncCleanup(stack.aclose)
        self.client = await stack.enter_async_context(
            phile.tmux.control_mode.open(
                phile.tmux.control_mode.Arguments()
            )
        )
        self.addCleanup(phile.tmux.kill_server)
        self.run_task = run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)

    async def test_exit_from_client_side(self) -> None:
        self.client.send_soon(phile.tmux.CommandBuilder.exit_client())
        await phile.asyncio.wait_for(self.run_task)

    async def test_server_terminates_early(self) -> None:
        """The server sends ``%exit`` when it is terminated."""
        await phile.asyncio.wait_for(phile.tmux.kill_server())
        await phile.asyncio.wait_for(self.run_task)
