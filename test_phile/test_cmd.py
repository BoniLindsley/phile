#!/usr/bin/env python3
"""
---------------------
Test :mod:`phile.cmd`
---------------------
"""

# Standard library.
import cmd
import io
import os
import typing
import unittest

# Internal packages.
import phile.asyncio
import phile.cmd


class _Cmd(cmd.Cmd):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.postcmd_called = False
        self.postloop_called = False
        self.precmd_called = False
        self.preloop_called = False

    def do_EOF(self, arg: str) -> typing.Literal[True]:
        del arg
        return True

    def postcmd(self, stop: bool, line: str) -> bool:
        self.postcmd_called = True
        return super().postcmd(stop, line)

    def postloop(self) -> None:
        self.postloop_called = True
        super().postloop()

    def precmd(self, line: str) -> str:
        self.precmd_called = True
        return super().precmd(line)

    def preloop(self) -> None:
        self.preloop_called = True
        super().preloop()


class _UsesCmd(unittest.TestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.stdin: io.StringIO
        self.stdout: io.StringIO
        self.cmd: _Cmd

    def setUp(self) -> None:
        super().setUp()
        self.stdin = io.StringIO()
        self.stdout = io.StringIO()
        self.cmd = _Cmd(stdin=self.stdin, stdout=self.stdout)


class TestProcessCommand(_UsesCmd, unittest.TestCase):
    """Tests :func:`~phile.cmd.process_command`."""

    def test_exits_without_command(self) -> None:
        self.assertTrue(phile.cmd.process_command(self.cmd, ''))

    def test_exits_with_eof(self) -> None:
        self.assertTrue(phile.cmd.process_command(self.cmd, 'EOF'))

    def test_run_precmd(self) -> None:
        self.assertFalse(self.cmd.precmd_called)
        phile.cmd.process_command(self.cmd, 'EOF')
        self.assertTrue(self.cmd.precmd_called)

    def test_run_postcmd(self) -> None:
        self.assertFalse(self.cmd.postcmd_called)
        phile.cmd.process_command(self.cmd, 'EOF')
        self.assertTrue(self.cmd.postcmd_called)


class TestAsyncCmdloopThreadedStdin(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.cmd: _Cmd
        self.stdin: typing.IO[str]
        self.stdin_writer: typing.IO[str]
        self.stdout: io.StringIO

    def setUp(self) -> None:
        super().setUp()
        reader_fd, writer_fd = os.pipe()

        def close(file_descriptor: int) -> None:
            try:
                os.close(file_descriptor)
            except OSError:
                pass

        self.addCleanup(close, reader_fd)
        self.addCleanup(close, writer_fd)
        self.stdin = open(  # pylint: disable=consider-using-with
            reader_fd, buffering=1
        )
        self.addCleanup(self.stdin.close)
        self.stdin_writer = open(  # pylint: disable=consider-using-with
            writer_fd, mode='w', buffering=1
        )
        self.addCleanup(self.stdin_writer.close)
        self.stdout = io.StringIO()
        self.cmd = _Cmd(stdin=self.stdin, stdout=self.stdout)

    async def test_exits_with_eof(self) -> None:
        self.stdin_writer.write('EOF\n')
        await phile.asyncio.wait_for(
            phile.cmd.async_cmdloop_threaded_stdin(
                looping_cmd=self.cmd,
            )
        )

    async def test_exits_if_eof_reached(self) -> None:
        self.stdin_writer.close()
        await phile.asyncio.wait_for(
            phile.cmd.async_cmdloop_threaded_stdin(
                looping_cmd=self.cmd,
            )
        )

    async def test_respects_intro(self) -> None:
        self.cmd.intro = 'Hello\n'
        await self.test_exits_if_eof_reached()
        self.assertEqual(self.stdout.getvalue(), 'Hello\n(Cmd) ')

    async def test_run_preloop(self) -> None:
        self.assertFalse(self.cmd.preloop_called)
        await self.test_exits_if_eof_reached()
        self.assertTrue(self.cmd.preloop_called)

    async def test_run_postloop(self) -> None:
        self.assertFalse(self.cmd.postloop_called)
        await self.test_exits_if_eof_reached()
        self.assertTrue(self.cmd.postloop_called)
