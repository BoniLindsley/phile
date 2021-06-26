#!/usr/bin/env python3
"""
-------------------------
Test :mod:`phile.asyncio`
-------------------------
"""

# Standard library.
import asyncio
import datetime
import os
import socket
import sys
import threading
import typing
import unittest
import unittest.mock

# Internal packages.
import phile.asyncio


class TestWaitForTimeout(unittest.TestCase):

    def test_default_value(self) -> None:
        self.assertEqual(
            phile.asyncio.wait_for_timeout.get(),
            datetime.timedelta(seconds=2),
        )

    def test_get_and_set(self) -> None:
        # Ensure get/set is detected in CI if somehow missing.
        timedelta = datetime.timedelta()
        reset_token = phile.asyncio.wait_for_timeout.set(timedelta)
        self.addCleanup(
            phile.asyncio.wait_for_timeout.reset, reset_token
        )
        self.assertEqual(phile.asyncio.wait_for_timeout.get(), timedelta)


class TestNoop(unittest.IsolatedAsyncioTestCase):

    async def test_callable(self) -> None:
        await phile.asyncio.wait_for(phile.asyncio.noop())


class TestWaitFor(unittest.IsolatedAsyncioTestCase):

    async def test_with_timeout(self) -> None:
        with self.assertRaises(asyncio.TimeoutError):
            await phile.asyncio.wait_for(
                phile.asyncio.noop(), timeout=datetime.timedelta()
            )

    async def test_custom_default_timeout(self) -> None:
        phile.asyncio.wait_for_timeout.set(datetime.timedelta())
        with self.assertRaises(asyncio.TimeoutError):
            await phile.asyncio.wait_for(phile.asyncio.noop())


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


class TestCancel(unittest.TestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.loop: asyncio.AbstractEventLoop

    def setUp(self) -> None:
        super().setUp()
        self.loop = loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)
        self.addCleanup(asyncio.set_event_loop, None)

    def test_cancels_existing_task(self) -> None:
        task_1 = self.loop.create_task(phile.asyncio.noop())
        task_2 = self.loop.create_task(phile.asyncio.noop())
        phile.asyncio.cancel({task_1, task_2})
        self.assertTrue(task_1.cancelled())
        self.assertTrue(task_2.cancelled())

    def test_ignores_if_done(self) -> None:
        task = self.loop.create_task(phile.asyncio.noop())
        self.loop.run_until_complete(task)
        phile.asyncio.cancel((task, ))
        self.assertFalse(task.cancelled())

    def test_ignores_if_already_cancelled_and_done(self) -> None:
        task = self.loop.create_task(phile.asyncio.noop())
        task.cancel()
        try:
            self.loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
        self.assertTrue(task.cancelled())
        phile.asyncio.cancel((task, ))

    def test_ignores_if_raises_and_done(self) -> None:

        async def raises() -> None:
            raise RuntimeError()

        task = self.loop.create_task(raises())
        try:
            self.loop.run_until_complete(task)
        except RuntimeError:
            pass
        phile.asyncio.cancel((task, ))

    def test_ignores_if_cancel_intercepted(self) -> None:

        async def waits_forever() -> None:
            try:
                await self.loop.create_future()
            except asyncio.CancelledError:
                pass

        task = self.loop.create_task(waits_forever())
        noop_task = self.loop.create_task(phile.asyncio.noop())
        self.loop.run_until_complete(noop_task)
        phile.asyncio.cancel((task, ))
        self.assertTrue(task.done())
        self.assertFalse(task.cancelled())


class TestHandleExceptions(unittest.TestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.exception_handler: unittest.mock.Mock
        self.loop: asyncio.AbstractEventLoop

    def setUp(self) -> None:
        super().setUp()
        self.loop = loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)
        self.addCleanup(asyncio.set_event_loop, None)
        self.exception_handler = exception_handler = unittest.mock.Mock()
        loop.set_exception_handler(exception_handler)

    def test_calls_handler_with_exception_dict(self) -> None:
        exception_to_raise = RuntimeError()

        async def raises() -> None:
            raise exception_to_raise

        task = self.loop.create_task(raises())
        try:
            self.loop.run_until_complete(task)
        except RuntimeError:
            pass
        phile.asyncio.handle_exceptions((task, ))
        self.exception_handler.assert_called_with(
            self.loop, {
                'message': 'Unhandled exception during loop shutdown.',
                'exception': exception_to_raise,
            }
        )

    def test_ignores_cancelled_tasks(self) -> None:
        task = self.loop.create_task(phile.asyncio.noop())
        phile.asyncio.cancel((task, ))
        phile.asyncio.handle_exceptions((task, ))
        self.exception_handler.assert_not_called()

    def test_ignores_returned_tasks(self) -> None:
        task = self.loop.create_task(phile.asyncio.noop())
        self.loop.run_until_complete(task)
        phile.asyncio.handle_exceptions((task, ))
        self.exception_handler.assert_not_called()

    def test_raises_if_not_done(self) -> None:
        task = self.loop.create_task(phile.asyncio.noop())
        self.addCleanup(self.loop.run_until_complete, task)
        with self.assertRaises(asyncio.InvalidStateError):
            phile.asyncio.handle_exceptions((task, ))


class TestClose(unittest.TestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.loop: asyncio.AbstractEventLoop

    def setUp(self) -> None:
        super().setUp()
        self.loop = loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)
        self.addCleanup(asyncio.set_event_loop, None)
        loop.set_exception_handler(lambda _loop, _context: None)

    def test_with_no_tasks(self) -> None:
        phile.asyncio.close()
        self.assertTrue(self.loop.is_closed())
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_cancels_existing_task(self) -> None:
        task = self.loop.create_task(phile.asyncio.noop())
        phile.asyncio.close()
        self.assertTrue(task.cancelled())


class TestOpenTask(unittest.IsolatedAsyncioTestCase):

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

    async def test_terminates_subprocess(self) -> None:
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


class TestQueue(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.queue: phile.asyncio.Queue[int]

    def setUp(self) -> None:
        super().setUp()
        self.queue = phile.asyncio.Queue()

    def test_close__can_be_called_on_new_instance(self) -> None:
        self.queue.close()

    def test_put_nowait__enqueues_item(self) -> None:
        self.queue.put_nowait(1)
        self.assertFalse(self.queue.empty())

    def test_put_nowait__raises_if_closed(self) -> None:
        self.queue.close()
        with self.assertRaises(phile.asyncio.QueueClosed):
            self.queue.put_nowait(1)

    async def test_put__enqueues_item(self) -> None:
        await self.queue.put(1)
        self.assertFalse(self.queue.empty())

    async def test_put__raises_if_closed(self) -> None:
        self.queue.close()
        with self.assertRaises(phile.asyncio.QueueClosed):
            await self.queue.put(1)

    def test_get_nowait__returns_put_nowait_value(self) -> None:
        self.queue.put_nowait(1)
        value = self.queue.get_nowait()
        self.assertEqual(value, 1)

    def test_get_nowait__raises_if_empty(self) -> None:
        with self.assertRaises(asyncio.QueueEmpty):
            self.queue.get_nowait()

    def test_get_nowait__raises_if_closed(self) -> None:
        self.queue.close()
        with self.assertRaises(phile.asyncio.QueueClosed):
            self.queue.get_nowait()

    def test_get_nowait__returns_remaining_value_if_closed(self) -> None:
        self.queue.put_nowait(1)
        self.queue.close()
        value = self.queue.get_nowait()
        self.assertEqual(value, 1)
        with self.assertRaises(phile.asyncio.QueueClosed):
            self.queue.get_nowait()

    async def test_get__returns_put_value(self) -> None:
        await self.queue.put(1)
        value = await self.queue.get()
        self.assertEqual(value, 1)

    async def test_get__waits_if_empty(self) -> None:
        getter = asyncio.create_task(self.queue.get())
        await asyncio.sleep(0)
        self.assertFalse(getter.done())
        await self.queue.put(1)
        value = await self.queue.get()
        self.assertEqual(value, 1)

    async def test_get__raises_if_closed(self) -> None:
        self.queue.close()
        with self.assertRaises(phile.asyncio.QueueClosed):
            await self.queue.get()

    async def test_get__returns_remaining_value_if_closed(self) -> None:
        await self.queue.put(1)
        self.queue.close()
        value = await self.queue.get()
        self.assertEqual(value, 1)
        with self.assertRaises(phile.asyncio.QueueClosed):
            await self.queue.get()

    async def test_get__raises_if_closed_while_waiting(self) -> None:
        getter = asyncio.create_task(self.queue.get())
        await asyncio.sleep(0)
        self.queue.close()
        with self.assertRaises(phile.asyncio.QueueClosed):
            await getter


class TestThreadedTextIOBase(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.stream_reader: typing.IO[str]
        self.stream_writer: typing.IO[str]
        self.threaded_stream: phile.asyncio.ThreadedTextIOBase

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        reader_fd, writer_fd = os.pipe()

        def close(file_descriptor: int) -> None:
            try:
                os.close(file_descriptor)
            except OSError:
                pass

        self.addCleanup(close, reader_fd)
        self.addCleanup(close, writer_fd)
        self.stream_reader = open(  # pylint: disable=consider-using-with
            reader_fd, buffering=1
        )
        self.addCleanup(self.stream_reader.close)
        self.stream_writer = open(  # pylint: disable=consider-using-with
            writer_fd, mode='w', buffering=1
        )
        self.addCleanup(self.stream_writer.close)
        self.threaded_stream = phile.asyncio.ThreadedTextIOBase(
            self.stream_reader
        )

    async def test_readline__reads_one_line(self) -> None:
        expected_line = 'One line.\n'
        self.stream_writer.write(expected_line)
        next_line = await phile.asyncio.wait_for(
            self.threaded_stream.readline()
        )
        self.assertEqual(next_line, expected_line)

    async def test_readline__raises_if_closed(self) -> None:
        self.stream_writer.close()
        with self.assertRaises(ValueError):
            await phile.asyncio.wait_for(self.threaded_stream.readline())

    async def test_readline__raises_if_closed_while_waiting(
        self
    ) -> None:
        # Send two tasks to wait for more lines.
        # But only give one of them a line.
        reading_tasks = {
            asyncio.create_task(self.threaded_stream.readline()),
            asyncio.create_task(self.threaded_stream.readline()),
        }
        self.stream_writer.write('Line before closing.\n')
        done, pending = await asyncio.wait(
            reading_tasks,
            timeout=phile.asyncio.wait_for_timeout.get().total_seconds(),
            return_when=asyncio.FIRST_COMPLETED
        )
        del done
        self.assertEqual(len(pending), 1)
        # Since the two tasks run in parallel,
        # we can be somewhat sure the other task is now waiting.
        # Give it one more chance to catch up.
        await asyncio.sleep(0)
        # Now we can test what happens if the stream closes
        # while waiting for another line.
        self.stream_writer.close()
        with self.assertRaises(ValueError):
            await phile.asyncio.wait_for(pending.pop())

    async def test_close__forces_readline_to_raise(self) -> None:
        self.threaded_stream.close()
        with self.assertRaises(ValueError):
            await phile.asyncio.wait_for(self.threaded_stream.readline())
