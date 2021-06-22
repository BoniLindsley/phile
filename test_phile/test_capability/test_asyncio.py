#!/usr/bin/env python3

# Standard libraries.
import asyncio
import unittest
import unittest.mock

# Internal packages.
import phile.capability
import phile.capability.asyncio


class TestProvideLoops(unittest.TestCase):

    def test_add_capability(self) -> None:
        capability_registry = phile.capability.Registry()
        with phile.capability.asyncio.provide_loop(
            capability_registry=capability_registry,
        ) as loop:
            self.assertFalse(loop.is_closed())
            self.assertIn(asyncio.AbstractEventLoop, capability_registry)
        self.assertTrue(loop.is_closed())
        self.assertNotIn(asyncio.AbstractEventLoop, capability_registry)

    def test_forwards_exceptions_to_current_handler(self) -> None:
        exception_to_raise = RuntimeError()

        async def raises_runtime_error() -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass
            raise exception_to_raise

        capability_registry = phile.capability.Registry()
        with phile.capability.asyncio.provide_loop(
            capability_registry=capability_registry,
        ) as loop:
            error_task = loop.create_task(raises_runtime_error())
            loop.set_exception_handler(handler := unittest.mock.Mock())
            loop.call_soon(loop.stop)
            loop.run_forever()
        self.assertFalse(error_task.cancelled())
        self.assertTrue(error_task.done())
        handler.assert_called_with(
            loop, {
                'message': 'Unhandled exception during loop shutdown.',
                'exception': exception_to_raise,
            }
        )
