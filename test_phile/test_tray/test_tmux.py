#!/usr/bin/env python3
"""
--------------------
Test phile.tray.tmux
--------------------
"""

# Standard library.
import asyncio
import contextlib
import datetime
import functools
import logging
import os
import pathlib
import pty
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import typing
import unittest
import unittest.mock

# External dependencies.
import psutil  # type: ignore[import]
import watchdog.events  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.tray
from phile.tray.tmux import (
    CommandBuilder, kill_server, timedelta_to_seconds
)
from test_phile.pyside2_test_tools import EnvironBackup
import test_phile.threaded_mock

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""

wait_time = datetime.timedelta(seconds=2)


def wait(
    coroutine: typing.Union[typing.Coroutine, asyncio.Task]
) -> asyncio.Future:
    return asyncio.wait_for(coroutine, timeout=wait_time.total_seconds())


class TestCommandBuilder(unittest.TestCase):
    """
    Tests :class:`~phile.tray.tmux.CommandBuilder`.

    Ensures the tmux command string returned from the class methods
    are as expected.
    """

    def test_exit_client(self) -> None:
        self.assertEqual(CommandBuilder.exit_client(), '')

    def test_refresh_client(self) -> None:
        self.assertEqual(
            CommandBuilder.refresh_client(), 'refresh-client'
        )
        self.assertEqual(
            CommandBuilder.refresh_client(no_output=False),
            'refresh-client -F \'\''
        )
        self.assertEqual(
            CommandBuilder.refresh_client(no_output=True),
            'refresh-client -F no-output'
        )

    def test_set_destroy_unattached(self) -> None:
        self.assertEqual(
            CommandBuilder.set_destroy_unattached(False),
            'set-option destroy-unattached off'
        )
        self.assertEqual(
            CommandBuilder.set_destroy_unattached(True),
            'set-option destroy-unattached on'
        )

    def test_set_global_status_right(self) -> None:
        self.assertEqual(
            CommandBuilder.set_global_status_right(''),
            "set-option -g status-right ''"
        )
        self.assertEqual(
            CommandBuilder.set_global_status_right("'"),
            (
                'set-option -g status-right '
                # Not quite what I want,
                # but it is what `shlex.quote` gives and it is valid.
                # Empty  open  char  close  empty
                # `''     "     '     "     ''`
                + "''" + '"' + "'" + '"' + "''"
            )
        )

    def test_unset_global_status_right(self) -> None:
        self.assertEqual(
            CommandBuilder.unset_global_status_right(),
            "set-option -gu status-right"
        )


class TestTimedeltaToSeconds(unittest.TestCase):
    """Tests :class:`~phile.tray.tmux.timedelta_to_seconds`."""

    def test_timedelta(self) -> None:
        """Convert :class:`~datetime.timedelta` to seconds."""
        timedelta = datetime.timedelta(hours=2)
        result = timedelta_to_seconds(timedelta)
        self.assertEqual(result, 2 * 60 * 60)
        self.assertIsInstance(result, float)

    def test_none(self) -> None:
        """Keep :data:`None` as is."""
        self.assertEqual(timedelta_to_seconds(None), None)


class TestControlModeArguments(unittest.TestCase):
    """Tests :class:`~phile.tray.tmux.ControlModeArguments`."""

    def test_default(self) -> None:
        """Default joins ``ctrl`` session with no configuration."""
        arguments = phile.tray.tmux.ControlModeArguments()
        self.assertEqual(
            arguments.to_list(),
            ['-CC', '-u', 'new-session', '-A', '-s', 'ctrl']
        )

    def test_no_session(self) -> None:
        """Session name can be removed to create a new session."""
        arguments = phile.tray.tmux.ControlModeArguments(session_name='')
        self.assertEqual(arguments.to_list(), ['-CC', '-u'])

    def test_custom_configuration(self) -> None:
        """Server configuration can be changed."""
        arguments = phile.tray.tmux.ControlModeArguments(
            tmux_configuration_path=pathlib.Path('conf')
        )
        self.assertEqual(
            arguments.to_list(), [
                '-CC', '-u', '-f', 'conf', 'new-session', '-A', '-s',
                'ctrl'
            ]
        )


class TestCloseSubprocess(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.tray.tmux.close_subprocess`."""

    async def test_terminates_subprocess(self) -> None:
        """It should terminate the subprocess."""
        program = sys.executable
        subprocess = await asyncio.create_subprocess_exec(program)
        self.addCleanup(
            lambda: subprocess.kill()
            if subprocess.returncode is None else None
        )
        assert subprocess.returncode is None
        assert subprocess.stdin is None
        assert subprocess.stdout is None
        assert subprocess.stderr is None
        await phile.tray.tmux.close_subprocess(subprocess)
        self.assertIsNotNone(subprocess.returncode)

    async def test_closes_automatic_pipes(self) -> None:
        """It should close any automatically created pipes."""
        program = sys.executable
        subprocess = await asyncio.create_subprocess_exec(
            program,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.addCleanup(
            lambda: subprocess.kill()
            if subprocess.returncode is None else None
        )
        assert subprocess.returncode is None
        assert subprocess.stdin is not None
        assert subprocess.stdout is not None
        assert subprocess.stderr is not None
        await phile.tray.tmux.close_subprocess(subprocess)
        self.assertIsNotNone(subprocess.returncode)
        self.assertTrue(subprocess.stdin.is_closing())
        self.assertTrue(subprocess.stdout.at_eof())
        self.assertTrue(subprocess.stderr.at_eof())


class TestControlModeProtocol(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.tray.tmux.ControlModeProtocol`."""

    async def asyncSetUp(self) -> None:
        loop = asyncio.get_running_loop()
        reader, self.sender = socket.socketpair()
        self.addCleanup(reader.close)
        self.addCleanup(self.sender.close)
        self.protocol: phile.tray.tmux.ControlModeProtocol
        transport, self.protocol = (
            await loop.connect_read_pipe(  # type: ignore[assignment]
                phile.tray.tmux.ControlModeProtocol, reader
            )
        )
        self.addCleanup(transport.close)

    async def test_data_received(self) -> None:
        """New lines are detected as data are received."""
        self.sender.send(b'\r\n')
        await wait(self.protocol.new_data_received.wait())

    async def test_peek_line(self) -> None:
        """Can check a line which tmux says ends with ``\\r\\n``."""
        self.sender.send(b'line-1\n\r\n\r')
        line = await wait(self.protocol.peek_line())
        self.assertEqual(line, b'line-1\n\r\n')
        line = await wait(self.protocol.peek_line())
        self.assertEqual(line, b'line-1\n\r\n')

    async def test_read_line(self) -> None:
        """Can read a line which tmux defines as ending with ``\r\n``."""
        self.sender.send(b'line-1\n\r\n\r')
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, 'line-1\n\r\n')

    async def test_read_line_with_two_lines(self) -> None:
        """Can read each line separately even if received together."""
        self.sender.send(b'line-1\n\r\n\nline-2\r\n')
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, 'line-1\n\r\n')
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, '\nline-2\r\n')

    async def test_read_line_merges_trailing_lines(self) -> None:
        """Can read a line that was broken up when sending."""
        self.sender.send(b'line-1\n\r')
        self.sender.send(b'\n\nline-2')
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, 'line-1\n\r\n')

    async def test_remove_prefix_after_reading_line(self) -> None:
        """Remove prefix from the first line."""
        self.sender.send(b'\x1bP1000p%begin\r\n')
        prefix = b'\x1bP1000p'
        await wait(self.protocol.remove_prefix(prefix))
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_remove_prefix_without_new_line(self) -> None:
        self.sender.send(b'\x1b\\')
        prefix = b'\x1b\\'
        await wait(self.protocol.remove_prefix(prefix))
        self.sender.send(b'%begin\r\n')
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_remove_prefix_without_new_line_or_drain(self) -> None:
        self.sender.send(b'\x1b\\%be')
        prefix = b'\x1b\\'
        await wait(self.protocol.remove_prefix(prefix))
        self.sender.send(b'gin\r\n')
        line = await wait(self.protocol.read_line())
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
        await wait(self.protocol.new_data_received.wait())
        self.sender.send(b'in')
        await wait(remove_task)
        self.sender.send(b'%end\r\n')
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, '%end\r\n')

    async def test_remove_prefix_raises_if_not_found_in_line(
        self
    ) -> None:
        self.sender.send(b'%begin\r\n')
        prefix = b'\x1bP1000p'
        with self.assertRaises(
            phile.tray.tmux.ControlModeProtocol.PrefixNotFound
        ):
            await wait(self.protocol.remove_prefix(prefix))
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_remove_prefix_raises_if_not_found_in_buffer(
        self
    ) -> None:
        self.sender.send(b'%begin')
        prefix = b'no'
        with self.assertRaises(
            phile.tray.tmux.ControlModeProtocol.PrefixNotFound
        ):
            await wait(self.protocol.remove_prefix(prefix))
        self.sender.send(b'\r\n')
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_remove_prefix_raises_early_if_different(self) -> None:
        self.sender.send(b'%')
        prefix = b'\x1b\\'
        with self.assertRaises(
            phile.tray.tmux.ControlModeProtocol.PrefixNotFound
        ):
            await wait(self.protocol.remove_prefix(prefix))
        self.sender.send(b'begin\r\n')
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, '%begin\r\n')

    async def test_drop_lines_until_starts_with(self) -> None:
        self.sender.send(b'line-1\n\r\n%beginner\r\n%endder\r\n')
        line = await wait(
            self.protocol.drop_lines_until_starts_with('%begin')
        )
        self.assertEqual(line, '%beginner\r\n')
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, '%endder\r\n')

    async def test_read_lines_until_starts_with(self) -> None:
        """Record lines until a specifix prefix is found."""
        self.sender.send(b'line-1\n\r\n%beginner\r\n%endder\r\n')
        line = await wait(
            self.protocol.read_lines_until_starts_with('%begin')
        )
        self.assertEqual(line, ['line-1\n\r\n', '%beginner\r\n'])
        line = await wait(self.protocol.read_line())
        self.assertEqual(line, '%endder\r\n')

    async def test_read_block(self) -> None:
        """Reading a block between ``%begin`` and ``%end``."""
        self.sender.send(b'line-1\n\r\n%begin er\r\n%end er\r\n')
        content = await wait(self.protocol.read_block())
        self.assertEqual(content, ['%begin er\r\n', '%end er\r\n'])


class HasClient(unittest.IsolatedAsyncioTestCase):

    async def async_set_up_client(self) -> None:
        """Create sockets to send fake tmux messages."""
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        server_socket, client_socket = socket.socketpair()
        stack.enter_context(server_socket)
        stack.enter_context(client_socket)
        self.server = server_socket
        server_socket.setblocking(False)
        loop = asyncio.get_running_loop()
        transport: asyncio.WriteTransport
        protocol: phile.tray.tmux.ControlModeProtocol
        transport, protocol = (
            await loop.create_connection(  # type: ignore[assignment]
                phile.tray.tmux.ControlModeProtocol, sock=client_socket
            )
        )
        self.addCleanup(transport.close)
        self.subprocess = subprocess = unittest.mock.Mock()
        self.subprocess_stopped = subprocess_stopped = asyncio.Event()
        subprocess.wait = subprocess_stopped.wait
        self.client = phile.tray.tmux.ControlMode(
            transport=transport,
            protocol=protocol,
            subprocess=subprocess
        )
        self.server_sendall = (
            lambda data: asyncio.create_task(
                asyncio.get_running_loop().
                sock_sendall(server_socket, data)
            )
        )


class TestControlMode(HasClient, unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.tray.tmux.ControlMode`."""

    async def asyncSetUp(self) -> None:
        await self.async_set_up_client()

    async def test_run_returns_on_immediate_disconnect(self) -> None:
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        self.server.close()
        await wait(run_task)

    async def test_run_returns_on_disconnect_after_startup(self) -> None:
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')
        self.server.close()
        await wait(run_task)

    async def test_send_soon_does_send_eventually(self) -> None:
        loop = asyncio.get_running_loop()
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')
        self.client.send_soon(CommandBuilder.exit_client())
        line = await wait(loop.sock_recv(self.server, 1))
        self.assertEqual(line, b'\n')

    async def test_run_can_terminate_to_exit_response(self) -> None:
        loop = asyncio.get_running_loop()
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')
        await self.server_sendall(b'%exit\r\n\x1b\\')
        await wait(run_task)

    async def test_run_can_terminate_to_a_disconnect(self) -> None:
        loop = asyncio.get_running_loop()
        run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)
        self.server.close()
        await wait(run_task)


class TestOpenControlMode(unittest.IsolatedAsyncioTestCase):
    """
    Tests :func:`~phile.tray.tmux.open_control_mode`.

    Integration test on whether ``tmux`` can be communicated with.
    """

    def setUp(self) -> None:
        """
        Create a tmux server instance before each method test.

        It has to be created in order for the control mode client
        to connect to it for testing purposes.
        A new one is created for each test
        to make sure no server state information
        would interfere with each other.

        The tmux server creates a socket file
        inside the directory ``$TMUX_TMPDIR``.
        We use a temporary directory so it is guaranteed
        to not interfere with other tests
        or any running tmux servers.

        Also creates an empty configuration file
        so that tmux does not use the OS default nor the user one.
        """
        _logger.debug('Creating $TMUX_TMPDIR directory.')
        tmux_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmux_tmpdir.cleanup)
        tmux_tmpdir_path = pathlib.Path(tmux_tmpdir.name)
        _logger.debug('Creating tmux.conf.')
        tmux_config_path = tmux_tmpdir_path / 'tmux.conf'
        tmux_config_path.touch()
        _logger.debug('Setting environment variables.')
        environ_backup = EnvironBackup()
        self.addCleanup(environ_backup.restore)
        environ_backup.backup_and_set(
            TMUX=None,
            TMUX_TMPDIR=str(tmux_tmpdir_path),
        )
        self.control_mode_arguments = (
            phile.tray.tmux.ControlModeArguments()
        )

    async def asyncSetUp(self) -> None:
        self.stack = stack = contextlib.AsyncExitStack()
        self.addAsyncCleanup(stack.aclose)
        self.client = await stack.enter_async_context(
            phile.tray.tmux.open_control_mode(
                self.control_mode_arguments
            )
        )
        self.addCleanup(kill_server)
        self.run_task = run_task = asyncio.create_task(self.client.run())
        self.addCleanup(run_task.cancel)

    async def test_exit_from_client_side(self) -> None:
        self.client.send_soon(
            phile.tray.tmux.CommandBuilder.exit_client()
        )
        await wait(self.run_task)

    async def test_server_terminates_early(self) -> None:
        """The server sends ``%exit`` when it is terminated."""
        phile.tray.tmux.kill_server()
        await wait(self.run_task)


class TestStatusRight(HasClient, unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.tray.tmux.StatusRight`."""

    async def asyncSetUp(self) -> None:
        await self.async_set_up_client()
        client_task = asyncio.create_task(self.client.run())
        self.addCleanup(client_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')
        self.status_right = phile.tray.tmux.StatusRight(
            control_mode=self.client
        )

    async def check_server_recieves(self, command: str) -> None:
        expected_data = command.encode() + b'\n'
        data = await wait(
            asyncio.get_running_loop().sock_recv(
                self.server, len(expected_data)
            )
        )
        self.assertEqual(expected_data, data)
        await self.server_sendall(b'%begin 1\r\n%end 1\r\n')

    async def check_status_right_set_to(self, tray_text: str) -> None:
        command = phile.tray.tmux.CommandBuilder.set_global_status_right(
            tray_text
        )
        await self.check_server_recieves(command)

    async def test_set(self) -> None:
        tray_text = 'Status right set'
        self.status_right.set(tray_text)
        await self.check_status_right_set_to(tray_text)

    async def test_set_to_same_value_does_not_send_command(self) -> None:
        """Setting to the cached value does nothing."""
        tray_text = 'Status right set'
        self.status_right.set(tray_text)
        await self.check_status_right_set_to(tray_text)
        self.status_right.set(tray_text)
        self.assertTrue(self.client._commands.empty())

    async def test_use_as_context_manager(self) -> None:
        with self.status_right as status_right:
            await self.check_status_right_set_to('')
        await self.check_server_recieves(
            phile.tray.tmux.CommandBuilder.unset_global_status_right()
        )
        await self.server_sendall(b'%begin 1\r\n%end 1\r\n')


class TestTrayFilesToTrayText(unittest.TestCase):
    """Tests :func:`~phile.tray.tmux.StatusRight`."""

    def test_merge(self) -> None:
        File = phile.tray.File
        self.assertEqual(
            phile.tray.tmux.tray_files_to_tray_text(
                files=[
                    File(path=pathlib.Path(), text_icon='Tray'),
                    File(path=pathlib.Path(), text_icon='Files'),
                    File(path=pathlib.Path(), text_icon='To'),
                    File(path=pathlib.Path(), text_icon='Tray'),
                    File(path=pathlib.Path(), text_icon='Text'),
                ]
            ), 'TrayFilesToTrayText'
        )


class TestReadByte(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.tray.tmux.read_byte`."""

    async def test_run(self) -> None:
        server, client = socket.socketpair()
        self.addCleanup(server.close)
        self.addCleanup(client.close)
        server.sendall(b'x')
        await wait(phile.tray.tmux.read_byte(client))


class CompletionCheckingThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon = True
        self.completed_event = threading.Event()

    def run(self):
        super().run()
        # If run raised an exception,
        # the event would not be set here.
        self.completed_event.set()


class TestRun(HasClient, unittest.IsolatedAsyncioTestCase):
    """Tests :class:`~phile.tray.tmux.run`."""

    def set_up_configuration(self) -> None:
        """Use unique data directories for each test."""
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )

    def set_up_observer(self) -> None:
        """
        Use unique observers to ensure handlers do not linger.

        Start immediately to allow file changes to propagate.
        The observer does not join, as that can take a long time.
        Stopping it should be sufficient.
        """
        self.observer = observer = watchdog.observers.Observer()
        observer.daemon = True
        observer.start()
        self.addCleanup(observer.stop)

    async def async_set_up_reply(self) -> None:
        self.control_mode = self.client
        self.client_task = client_task = (
            asyncio.create_task(self.client.run())
        )
        self.addCleanup(client_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')

    async def async_set_up_run(self) -> None:
        self.run_task = run_task = asyncio.create_task(
            phile.tray.tmux.run(
                configuration=self.configuration,
                control_mode=self.client,
                watching_observer=self.observer,
            )
        )
        self.addCleanup(run_task.cancel)
        await self.check_status_right_set_to('')

    async def asyncSetUp(self) -> None:
        self.set_up_configuration()
        self.set_up_observer()
        await wait(self.async_set_up_client())
        await wait(self.async_set_up_reply())

    async def check_server_recieves(self, command: str) -> None:
        expected_data = command.encode() + b'\n'
        data = await wait(
            asyncio.get_running_loop().sock_recv(
                self.server, len(expected_data)
            )
        )
        self.assertEqual(data, expected_data)
        await self.server_sendall(b'%begin 1\r\n%end 1\r\n')

    async def check_status_right_set_to(self, tray_text: str) -> None:
        command = phile.tray.tmux.CommandBuilder.set_global_status_right(
            tray_text
        )
        await self.check_server_recieves(command)

    async def test_returns_on_disconnect(self) -> None:
        """Close sends an exit request to tmux."""
        await self.async_set_up_run()
        self.server.close()
        await wait(self.run_task)

    async def test_checks_for_existing_files(self) -> None:
        """
        Showing should display existing tray files.

        Directory changes should be ignored.
        Wrong suffix should be ignored.
        """
        year_tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration,
            path_stem='year',
            text_icon='2345'
        )
        year_tray_file.save()
        self.year_tray_file = year_tray_file
        subdirectory = self.configuration.tray_directory / (
            'subdir' + self.configuration.tray_suffix
        )
        subdirectory.mkdir()
        wrong_tray_file = self.configuration.tray_directory / (
            'wrong' + self.configuration.tray_suffix + '_wrong'
        )
        wrong_tray_file.touch()
        await self.async_set_up_run()
        await self.check_status_right_set_to('2345')

    async def test_checks_for_file_changes(self) -> None:
        await self.test_checks_for_existing_files()
        year_tray_file = self.year_tray_file
        year_tray_file.text_icon = '3456'
        year_tray_file.save()
        await self.check_status_right_set_to(year_tray_file.text_icon)


if __name__ == '__main__':
    unittest.main()
