#!/usr/bin/env python3
"""
-------------------------
Test :mod:`phile.asyncio`
-------------------------
"""

# Standard library.
import asyncio
import datetime
import socket
import sys
import threading
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


class TestOpenTask(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.asyncio.open_task`."""

    async def test_cancels_given_task(self) -> None:
        task: (asyncio.Task[typing.Any]) = asyncio.create_task(
            asyncio.sleep(2048)
        )
        self.addCleanup(task.cancel)
        async with phile.asyncio.open_task(task) as returned_task:
            self.assertIs(returned_task, task)
            self.assertFalse(task.cancelled())
        with self.assertRaises(asyncio.CancelledError):
            await phile.asyncio.wait_for(task)

    async def test_creates_task_for_coroutine(self) -> None:

        async def sleep() -> None:
            await asyncio.sleep(2048)

        async with phile.asyncio.open_task(sleep()) as task:
            self.assertIsInstance(task, asyncio.Task)
        with self.assertRaises(asyncio.CancelledError):
            await phile.asyncio.wait_for(task)


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


class TestOpenReader(unittest.IsolatedAsyncioTestCase):
    """Tests :class:`~phile.asyncio.open_reader`."""

    def setUp(self) -> None:
        self.read_socket, self.write_socket = socket.socketpair()
        self.addCleanup(self.read_socket.close)
        self.addCleanup(self.write_socket.close)

    async def asyncSetUp(self) -> None:
        running_loop = asyncio.get_running_loop()
        self.addCleanup(running_loop.remove_reader, self.read_socket)

    async def test_init_accepts_socket_and_monitors_it(self) -> None:
        running_loop = asyncio.get_running_loop()
        with phile.asyncio.open_reader(self.read_socket, lambda: None):
            self.assertTrue(running_loop.remove_reader(self.read_socket))

    async def test_stops_monitoring_on_exit(self) -> None:
        running_loop = asyncio.get_running_loop()
        with phile.asyncio.open_reader(self.read_socket, lambda: None):
            pass
        self.assertFalse(running_loop.remove_reader(self.read_socket))

    async def test_calls_callback_on_readable(self) -> None:
        running_loop = asyncio.get_running_loop()
        callback_checker = asyncio.Event()
        with phile.asyncio.open_reader(
            self.read_socket, callback_checker.set
        ):
            running_loop.call_soon(self.write_socket.sendall, b'a')
            await phile.asyncio.wait_for(callback_checker.wait())


class TestReadable(unittest.IsolatedAsyncioTestCase):
    """Tests :class:`~phile.asyncio.readable`."""

    def setUp(self) -> None:
        self.read_socket, self.write_socket = socket.socketpair()
        self.addCleanup(self.read_socket.close)
        self.addCleanup(self.write_socket.close)

    async def asyncSetUp(self) -> None:
        running_loop = asyncio.get_running_loop()
        self.addCleanup(running_loop.remove_reader, self.read_socket)

    async def test_returns_when_readable(self) -> None:
        running_loop = asyncio.get_running_loop()
        running_loop.call_soon(self.write_socket.sendall, b'a')
        self.assertTrue(
            await phile.asyncio.wait_for(
                phile.asyncio.readable(self.read_socket)
            )
        )


class TestThread(unittest.IsolatedAsyncioTestCase):
    """Tests :class:`~phile.asyncio.Thread`."""

    async def test_async_join_returns_after_run(self) -> None:
        event = threading.Event()
        thread = phile.asyncio.Thread(target=event.set, daemon=True)
        thread.start()
        self.assertTrue(event.wait(timeout=2))
        await phile.asyncio.wait_for(thread.async_join())

    async def test_run_override_should_call_super_at_end(self) -> None:
        event = threading.Event()

        class Thread(phile.asyncio.Thread):

            def run(self) -> None:
                event.set()
                super().run()

        thread = Thread()
        thread.start()
        await phile.asyncio.wait_for(thread.async_join())
