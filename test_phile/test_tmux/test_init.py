#!/usr/bin/env python3
"""
----------------------
Test :mod:`phile.tmux`
----------------------
"""

# Standard library.
import asyncio
import pathlib
import tempfile
import unittest

# Internal packages.
import phile.asyncio
import phile.os
import phile.tmux


class TestCommandBuilder(unittest.TestCase):
    """
    Tests :class:`~phile.tmux.CommandBuilder`.

    Ensures the tmux command string returned from the class methods
    are as expected.
    """

    def test_exit_client(self) -> None:
        self.assertEqual(phile.tmux.CommandBuilder.exit_client(), '')

    def test_refresh_client(self) -> None:
        self.assertEqual(
            phile.tmux.CommandBuilder.refresh_client(), 'refresh-client'
        )
        self.assertEqual(
            phile.tmux.CommandBuilder.refresh_client(no_output=False),
            'refresh-client -F \'\''
        )
        self.assertEqual(
            phile.tmux.CommandBuilder.refresh_client(no_output=True),
            'refresh-client -F no-output'
        )

    def test_set_destroy_unattached(self) -> None:
        self.assertEqual(
            phile.tmux.CommandBuilder.set_destroy_unattached(False),
            'set-option destroy-unattached off'
        )
        self.assertEqual(
            phile.tmux.CommandBuilder.set_destroy_unattached(True),
            'set-option destroy-unattached on'
        )

    def test_set_global_status_right(self) -> None:
        self.assertEqual(
            phile.tmux.CommandBuilder.set_global_status_right(''),
            "set-option -g status-right ''"
        )
        self.assertEqual(
            phile.tmux.CommandBuilder.set_global_status_right("'"),
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
            phile.tmux.CommandBuilder.unset_global_status_right(),
            "set-option -gu status-right"
        )


class UsesTmux(unittest.TestCase):

    def setUp(self) -> None:
        """
        Set up ``tmux`` to launch an isolated instance if launched.

        It has to be set up for the control mode client
        to connect to it for testing purposes.
        A new server is created for each unit test
        to make sure no server state information
        would interfere with each other.

        The ``tmux`` server creates a socket file
        inside the directory ``$TMUX_TMPDIR``.
        A temporary directory is used to guarantee
        tests would not interfere with each other
        or any running ``tmux`` servers by the user.

        Also creates an empty configuration file
        so that ``tmux`` does not use the OS default nor the user one.
        There is no default option to change configuration file path.
        So this needs to be given to ``tmux`` via the `-f` flag.
        """
        super().setUp()
        tmux_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmux_tmpdir.cleanup)
        tmux_tmpdir_path = pathlib.Path(tmux_tmpdir.name)
        self.tmux_configuration_path = tmux_configuration_path = (
            tmux_tmpdir_path / 'tmux.conf'
        )
        tmux_configuration_path.touch()
        environ_backup = phile.os.Environ()
        self.addCleanup(environ_backup.restore)
        environ_backup.set(TMUX=None, TMUX_TMPDIR=str(tmux_tmpdir_path))


class UsesRunningTmuxServer(UsesTmux, unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        """Ensure tmux server has already started."""
        await super().asyncSetUp()
        tmux_client_one = await asyncio.create_subprocess_exec(
            'tmux',
            '-f',
            str(self.tmux_configuration_path),
            'new-session',
            '-d',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await phile.asyncio.wait_for(tmux_client_one.wait())
        except:
            if tmux_client_one.returncode is None:
                tmux_client_one.kill()
            raise
        self.assertEqual(tmux_client_one.returncode, 0)

        async def kill_server() -> None:
            killer = await phile.tmux.kill_server()
            await killer.wait()

        self.addAsyncCleanup(phile.asyncio.wait_for, kill_server())


class TestKillServer(
    UsesRunningTmuxServer, unittest.IsolatedAsyncioTestCase
):
    """Tests :func:`~phile.tmux.kill_server`."""

    async def test_does_kill_eventually(self) -> None:
        killer = await phile.asyncio.wait_for(phile.tmux.kill_server())
        await phile.asyncio.wait_for(killer.wait())
        self.assertEqual(killer.returncode, 0)

    async def test_returns_one_if_server_missing(self) -> None:
        await phile.asyncio.wait_for(self.test_does_kill_eventually())
        killer = await phile.asyncio.wait_for(phile.tmux.kill_server())
        await phile.asyncio.wait_for(killer.wait())
        self.assertEqual(killer.returncode, 1)
