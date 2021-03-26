#!/usr/bin/env python3

# Standard libraries.
import asyncio
import collections.abc
import contextlib
import threading
import typing

# Internal modules.
import phile.capability


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
    loop = asyncio.get_event_loop()
    pending_tasks = asyncio.all_tasks(loop)
    if not pending_tasks:
        return
    _cancel_tasks(pending_tasks)
    _check_task_exceptions(pending_tasks)


def _shutdown() -> None:
    loop = asyncio.get_event_loop()
    _cancel_all_tasks()
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.run_until_complete(loop.shutdown_default_executor())


def get_instance(
    capability_registry: phile.capability.Registry
) -> asyncio.AbstractEventLoop:
    Loop = asyncio.AbstractEventLoop
    return capability_registry[Loop]  # type: ignore[misc]


def stop(capability_registry: phile.capability.Registry) -> None:
    loop = get_instance(capability_registry)
    loop.stop()


def run(capability_registry: phile.capability.Registry) -> None:
    """
    Same as :func:`asyncio.run` but forever with a specified event loop.
    """
    with contextlib.ExitStack() as clean_up:
        loop = get_instance(capability_registry)
        clean_up.callback(loop.close)
        asyncio.set_event_loop(loop)
        clean_up.callback(asyncio.set_event_loop, None)
        clean_up.callback(_shutdown)
        loop.run_forever()


@contextlib.contextmanager
def start(
    capability_registry: phile.capability.Registry
) -> collections.abc.Iterator[None]:
    worker_thread = threading.Thread(
        target=run, args=(capability_registry, )
    )
    worker_thread.start()
    yield
    worker_thread.join()
