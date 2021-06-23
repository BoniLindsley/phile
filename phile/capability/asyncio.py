#!/usr/bin/env python3

# Standard libraries.
import asyncio
import collections.abc
import contextlib

# Internal modules.
import phile.asyncio
import phile.capability


@contextlib.contextmanager
def provide_loop(
    capability_registry: phile.capability.Registry,
) -> collections.abc.Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        try:
            with capability_registry.provide(
                loop, asyncio.AbstractEventLoop
            ):
                yield loop
        finally:
            asyncio.set_event_loop(loop)
            phile.asyncio.close()
    finally:
        loop.close()
