#!/usr/bin/env python3
"""
---------------------
Test :mod:`phile.cmd`
---------------------
"""

# Standard library.
import cmd
import io
import typing
import unittest
import unittest.mock

# Internal packages.
import phile
import phile.asyncio
import phile.cmd


class _Cmd(cmd.Cmd):

    def do_EOF(self, arg: str) -> typing.Literal[True]:
        del arg
        return True


class _UsesCmd(unittest.TestCase):

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
        with unittest.mock.patch.object(
            self.cmd, 'precmd', return_value='EOF'
        ) as precmd:
            phile.cmd.process_command(self.cmd, 'EOF')
            precmd.assert_called_with('EOF')

    def test_run_postcmd(self) -> None:
        with unittest.mock.patch.object(
            self.cmd, 'postcmd', return_value=True
        ) as postcmd:
            phile.cmd.process_command(self.cmd, 'EOF')
            postcmd.assert_called_with(True, 'EOF')


class TestAsyncCmdloopThreadedStdin(
    _UsesCmd, unittest.IsolatedAsyncioTestCase
):
    """Tests :func:`~phile.cmd.async_cmdloop_threaded_stdin`."""

    async def test_exits_with_eof(self) -> None:
        self.stdin.write('EOF\n')
        await phile.asyncio.wait_for(
            phile.cmd.async_cmdloop_threaded_stdin(
                looping_cmd=self.cmd,
            )
        )

    async def test_respects_intro(self) -> None:
        self.cmd.intro = 'Hello\n'
        self.stdin.write('EOF\n')
        await phile.asyncio.wait_for(
            phile.cmd.async_cmdloop_threaded_stdin(
                looping_cmd=self.cmd,
            )
        )
        self.assertEqual(self.stdout.getvalue(), 'Hello\n(Cmd) ')

    async def test_run_preloop(self) -> None:
        with unittest.mock.patch.object(self.cmd, 'preloop') as preloop:
            self.stdin.write('EOF\n')
            await phile.asyncio.wait_for(
                phile.cmd.async_cmdloop_threaded_stdin(
                    looping_cmd=self.cmd,
                )
            )
            preloop.assert_called_with()

    async def test_run_postloop(self) -> None:
        with unittest.mock.patch.object(
            self.cmd, 'postloop'
        ) as postloop:
            self.stdin.write('EOF\n')
            await phile.asyncio.wait_for(
                phile.cmd.async_cmdloop_threaded_stdin(
                    looping_cmd=self.cmd,
                )
            )
            postloop.assert_called_with()


if __name__ == '__main__':
    unittest.main()
