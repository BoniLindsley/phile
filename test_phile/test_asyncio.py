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
import sys
import typing
import unittest
import unittest.mock

# Internal packages.
import phile.asyncio


class TestWaitForTimeout(unittest.TestCase):
    """Tests :func:`~phile.asyncio.wait_for_timeout`."""

    def test_default_value(self) -> None:
        self.assertEqual(
            phile.asyncio.wait_for_timeout.get(),
            datetime.timedelta(seconds=2),
        )

    def test_get_and_set(self) -> None:
        """Ensure get/set is detected in CI if somehow missing."""
        timedelta = datetime.timedelta()
        reset_token = phile.asyncio.wait_for_timeout.set(timedelta)
        self.addCleanup(
            phile.asyncio.wait_for_timeout.reset, reset_token
        )
        self.assertEqual(phile.asyncio.wait_for_timeout.get(), timedelta)


class TestWaitFor(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.asyncio.wait_for`."""

    async def noop_coroutine(self) -> None:
        pass

    async def test_with_timeout(self) -> None:
        with self.assertRaises(asyncio.TimeoutError):
            await phile.asyncio.wait_for(
                self.noop_coroutine(), timeout=datetime.timedelta()
            )

    async def test_custom_default_timeout(self) -> None:
        phile.asyncio.wait_for_timeout.set(datetime.timedelta())
        with self.assertRaises(asyncio.TimeoutError):
            await phile.asyncio.wait_for(self.noop_coroutine())


class TestCloseSubprocess(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.asyncio.close_subprocess`."""

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
        await phile.asyncio.wait_for(
            phile.asyncio.close_subprocess(subprocess)
        )
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
        await phile.asyncio.wait_for(
            phile.asyncio.close_subprocess(subprocess)
        )
        self.assertIsNotNone(subprocess.returncode)
        self.assertTrue(subprocess.stdin.is_closing())
        self.assertTrue(subprocess.stdout.at_eof())
        self.assertTrue(subprocess.stderr.at_eof())
