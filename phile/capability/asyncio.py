#!/usr/bin/env python3

# Standard libraries.
import asyncio
import collections.abc
import contextlib
import logging
import typing

# Internal modules.
import phile.capability

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)


def _cancel_tasks(
    tasks_to_cancel: collections.abc.Iterable[asyncio.Task[typing.Any]]
) -> None:
    loop = asyncio.get_event_loop()
    gatherer = asyncio.gather(*tasks_to_cancel, return_exceptions=True)
    gatherer.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        loop.run_until_complete(gatherer)


def _check_task_exceptions(
    tasks: collections.abc.Iterable[asyncio.Task[typing.Any]]
) -> None:
    _logger.debug('Checking asyncio task exceptions.')
    loop = asyncio.get_event_loop()
    possible_exceptions = (
        task.exception() for task in tasks if not task.cancelled()
    )
    raised_exceptions = (
        exception for exception in possible_exceptions
        if exception is not None
    )
    handle_exception = loop.call_exception_handler
    for exception in raised_exceptions:
        handle_exception({
            'message': 'Unhandled exception during loop shutdown.',
            'exception': exception,
        })


def _cancel_all_tasks() -> None:
    _logger.debug('Cancelling existing asyncio tasks.')
    loop = asyncio.get_event_loop()
    pending_tasks = asyncio.all_tasks(loop)
    if not pending_tasks:
        return
    _cancel_tasks(pending_tasks)
    _check_task_exceptions(pending_tasks)


def _shutdown() -> None:
    loop = asyncio.get_event_loop()
    _cancel_all_tasks()
    _logger.debug('Shutting down asyncio loop states.')
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.run_until_complete(loop.shutdown_default_executor())


@contextlib.contextmanager
def provide_loop(
    capability_registry: phile.capability.Registry,
) -> collections.abc.Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        try:
            with capability_registry.provide(
                loop,
                asyncio.AbstractEventLoop,
            ):
                yield loop
        finally:
            asyncio.set_event_loop(loop)
            _shutdown()
            asyncio.set_event_loop(None)
    finally:
        loop.close()
