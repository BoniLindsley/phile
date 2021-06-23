#!/usr/bin/env python3

# Standard libraries.
import asyncio
import unittest

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
