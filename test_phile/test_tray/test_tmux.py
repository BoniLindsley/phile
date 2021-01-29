#!/usr/bin/env python3
"""
---------------------------
Test :mod:`phile.tray.tmux`
---------------------------
"""

# Standard library.
import asyncio
import pathlib
import socket
import tempfile
import unittest

# External dependencies.
import watchdog.observers

# Internal packages.
import phile.asyncio
import phile.configuration
import phile.tmux
import phile.tmux.control_mode
import phile.tray
import phile.tray.tmux
from test_phile.test_tmux.test_control_mode import (
    UsesClientWithFakeSubprocess
)


class TestStatusRight(
    UsesClientWithFakeSubprocess, unittest.IsolatedAsyncioTestCase
):
    """Tests :func:`~phile.tray.tmux.StatusRight`."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        client_task = asyncio.create_task(self.client.run())
        self.addCleanup(client_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')
        self.status_right = phile.tray.tmux.StatusRight(
            control_mode=self.client
        )

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
            phile.tmux.CommandBuilder.unset_global_status_right()
        )
        await self.server_sendall(b'%begin 1\r\n%end 1\r\n')


class TestTrayFilesToTrayText(unittest.TestCase):
    """Tests :func:`~phile.tray.tmux.tray_files_to_tray_text`."""

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


class TestRun(
    UsesClientWithFakeSubprocess, unittest.IsolatedAsyncioTestCase
):
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

    def setUp(self) -> None:
        super().setUp()
        self.set_up_configuration()
        self.set_up_observer()

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await phile.asyncio.wait_for(self.async_set_up_reply())

    async def test_returns_on_disconnect(self) -> None:
        """Close sends an exit request to tmux."""
        await self.async_set_up_run()
        self.server.close()
        await phile.asyncio.wait_for(self.run_task)

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


class TestReadByte(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.tray.tmux.read_byte`."""

    async def test_run(self) -> None:
        server, client = socket.socketpair()
        self.addCleanup(server.close)
        self.addCleanup(client.close)
        server.sendall(b'x')
        await phile.asyncio.wait_for(phile.tray.tmux.read_byte(client))
