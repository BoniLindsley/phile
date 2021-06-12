#!/usr/bin/env python3
"""
-------------------------
Test :mod:`phile.asyncio`
-------------------------
"""

# Standard library.
import asyncio
import datetime
import io
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


class SomethingBadHappened(Exception):
    pass


class TestCancelAndWait(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.target: asyncio.Future[int]
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.target = asyncio.get_running_loop().create_future()

    async def cancel_and_wait(self) -> typing.Optional[int]:
        # If `coroutine` is inlined into `wait_for`,
        # then mypy expects `self.target` to be `typing.Optional[int]`.
        # Not sure how to fix that.
        coroutine = phile.asyncio.cancel_and_wait(self.target)
        result = await phile.asyncio.wait_for(coroutine)
        return result

    async def test_cancels_given_future(self) -> None:
        result = await self.cancel_and_wait()
        self.assertTrue(self.target.cancelled())
        self.assertIsNone(result)

    async def test_ignores_if_already_cancelled(self) -> None:
        await self.cancel_and_wait()
        result = await self.cancel_and_wait()
        self.assertIsNone(result)

    async def test_retrieves_result(self) -> None:
        self.target.set_result(0)
        result = await self.cancel_and_wait()
        self.assertEqual(result, 0)

    async def test_propagates_exception(self) -> None:
        self.target.set_exception(SomethingBadHappened())
        with self.assertRaises(SomethingBadHappened):
            await self.cancel_and_wait()

    async def test_propagates_cancelled_exception(self) -> None:
        self.target.set_exception(asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await self.cancel_and_wait()


class TestOpenTask(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.asyncio.open_task`."""

    async def test_cancels_given_task(self) -> None:
        task: (asyncio.Task[typing.Any]) = asyncio.create_task(
            asyncio.Event().wait()
        )
        self.addCleanup(task.cancel)
        with self.assertRaises(asyncio.CancelledError):
            async with phile.asyncio.open_task(task) as returned_task:
                self.assertIs(returned_task, task)
                self.assertFalse(task.cancelled())
        self.assertTrue(task.cancelled())

    async def test_creates_task_for_coroutine(self) -> None:
        with self.assertRaises(asyncio.CancelledError):
            async with phile.asyncio.open_task(
                asyncio.Event().wait()
            ) as task:
                self.assertIsInstance(task, asyncio.Task)

    async def test_suppress_cancelled_error_if_not_done(self) -> None:
        async with phile.asyncio.open_task(
            asyncio.Event().wait(),
            suppress_cancelled_error_if_not_done=True,
        ) as task:
            self.assertIsInstance(task, asyncio.Task)
        self.assertTrue(task.cancelled())


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


class EventThread(phile.asyncio.Thread):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.event = threading.Event()

    def run(self) -> None:
        self.event.set()
        super().run()


class SomeThreadError(Exception):
    pass


class TestThread(unittest.IsolatedAsyncioTestCase):
    """Tests :class:`~phile.asyncio.Thread`."""

    async def test_async_join_returns_after_run(self) -> None:
        event = threading.Event()
        thread = phile.asyncio.Thread(target=event.set, daemon=True)
        thread.start()
        self.assertTrue(event.wait(timeout=2))
        await phile.asyncio.wait_for(thread.async_join())

    async def test_run_override_should_call_super_at_end(self) -> None:
        thread = EventThread()
        thread.start()
        await phile.asyncio.wait_for(thread.async_join())
        self.assertTrue(thread.event.is_set())

    async def test_propagates_exception(self) -> None:

        def run() -> None:
            raise SomeThreadError()

        thread = phile.asyncio.Thread(target=run, daemon=True)
        thread.start()
        with self.assertRaises(SomeThreadError):
            await phile.asyncio.wait_for(thread.async_join())


class TestThreadedTextIOBase(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.stream = io.StringIO()
        self.threaded_stream = phile.asyncio.ThreadedTextIOBase(
            self.stream
        )

    async def test_reads_one_line(self) -> None:
        expected_line = 'Single file!\n'
        self.stream.write(expected_line)
        self.stream.seek(0)
        next_line = await phile.asyncio.wait_for(
            self.threaded_stream.readline()
        )
        self.assertEqual(next_line, expected_line)

    async def test_raises_if_closed(self) -> None:
        self.stream.close()
        with self.assertRaises(ValueError):
            await phile.asyncio.wait_for(self.threaded_stream.readline())
