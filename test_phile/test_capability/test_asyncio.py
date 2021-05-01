#!/usr/bin/env python3
"""
------------------------------------
Test :mod:`phile.capability.asyncio`
------------------------------------
"""

# Standard libraries.
import asyncio
import concurrent.futures
import contextlib
import functools
import unittest
import unittest.mock

# Internal packages.
import phile.capability
import phile.capability.asyncio


class TestProvide(unittest.TestCase):
    """Tests :func:`~phile.capability.asyncio.provide`."""

    def setUp(self) -> None:
        super().setUp()
        self.capability_registry = phile.capability.Registry()

    def test_add_capability(self) -> None:
        phile.capability.asyncio.provide(
            capability_registry=self.capability_registry
        )
        self.assertIn(
            asyncio.AbstractEventLoop, self.capability_registry
        )


class TestGetInstance(unittest.TestCase):
    """Tests :func:`~phile.capability.asyncio.get_instance`."""

    def setUp(self) -> None:
        super().setUp()
        self.capability_registry = phile.capability.Registry()
        phile.capability.asyncio.provide(
            capability_registry=self.capability_registry
        )

    def test_fetches_event_loop(self) -> None:
        loop = phile.capability.asyncio.get_instance(
            capability_registry=self.capability_registry
        )
        loop.run_until_complete(asyncio.sleep(0))


# TODO(BoniLindsley): Add time limit on test.
class TestRun(unittest.TestCase):
    """Tests :func:`~phile.capability.asyncio.run`."""

    def setUp(self) -> None:
        super().setUp()
        self.capability_registry = phile.capability.Registry()
        phile.capability.asyncio.provide(
            capability_registry=self.capability_registry
        )
        self.loop = phile.capability.asyncio.get_instance(
            capability_registry=self.capability_registry
        )

    def test_exits_when_stopped(self) -> None:
        self.loop.call_soon(self.loop.stop)
        phile.capability.asyncio.run(
            capability_registry=self.capability_registry
        )
        self.assertFalse(self.loop.is_running())


class TestStart(unittest.TestCase):
    """Tests :func:`~phile.capability.asyncio.start`."""

    def setUp(self) -> None:
        super().setUp()
        self.capability_registry = phile.capability.Registry()
        phile.capability.asyncio.provide(
            capability_registry=self.capability_registry
        )

    def test_returns_context_manager_for_clean_up(self) -> None:
        with phile.capability.asyncio.start(
            capability_registry=self.capability_registry
        ):
            phile.capability.asyncio.stop(
                capability_registry=self.capability_registry
            )


class TestStop(unittest.TestCase):
    """Tests :func:`~phile.capability.asyncio.stop`."""

    def setUp(self) -> None:
        super().setUp()
        self.capability_registry = phile.capability.Registry()
        phile.capability.asyncio.provide(
            capability_registry=self.capability_registry
        )
        self.loop = phile.capability.asyncio.get_instance(
            capability_registry=self.capability_registry
        )

    def test_stops_running_loop(self) -> None:
        self.loop.call_soon(
            functools.partial(
                phile.capability.asyncio.stop,
                capability_registry=self.capability_registry
            )
        )
        phile.capability.asyncio.run(
            capability_registry=self.capability_registry
        )
        self.assertFalse(self.loop.is_running())

    def test_stops_running_loop_from_coroutine(self) -> None:

        async def stop() -> None:
            phile.capability.asyncio.stop(
                capability_registry=self.capability_registry
            )

        stopper = self.loop.create_task(stop())
        phile.capability.asyncio.run(
            capability_registry=self.capability_registry
        )
        self.assertFalse(self.loop.is_running())
        self.assertTrue(stopper.done())

    def test_stops_started_loop(self) -> None:
        with phile.capability.asyncio.start(
            capability_registry=self.capability_registry
        ):
            phile.capability.asyncio.stop(
                capability_registry=self.capability_registry
            )
        self.assertFalse(self.loop.is_running())

    def test_stops_loop_stops_next_run_if_not_running(self) -> None:
        phile.capability.asyncio.stop(
            capability_registry=self.capability_registry
        )
        phile.capability.asyncio.run(
            capability_registry=self.capability_registry
        )

    def test_forwards_exceptions_to_handler(self) -> None:
        exception_to_raise = RuntimeError()

        async def raises_runtime_error() -> None:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.Event().wait()
            raise exception_to_raise

        error_task = self.loop.create_task(raises_runtime_error())
        self.loop.set_exception_handler(handler := unittest.mock.Mock())
        self.loop.call_soon(
            functools.partial(
                phile.capability.asyncio.stop,
                capability_registry=self.capability_registry
            )
        )
        phile.capability.asyncio.run(
            capability_registry=self.capability_registry
        )
        self.assertFalse(error_task.cancelled())
        self.assertTrue(error_task.done())
        handler.assert_called_with(
            self.loop, {
                'message': 'Unhandled exception during loop shutdown.',
                'exception': exception_to_raise,
            }
        )
