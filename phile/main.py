#!/usr/bin/env python3

# Standard library.
import asyncio
import collections.abc
import functools
import threading
import typing

# Internal packages.
import phile
import phile.capability
import phile.capability.asyncio
import phile.launcher
import phile.launcher.defaults

_T = typing.TypeVar('_T')
Awaitable = collections.abc.Awaitable[_T]
Registry = phile.capability.Registry
AsyncTarget = collections.abc.Callable[[Registry], Awaitable[_T]]


async def _async_run(
    async_target: AsyncTarget[_T],
    capability_registry: Registry,
) -> _T:  # pragma: no cover
    async with phile.launcher.provide_registry(
        capability_registry=capability_registry
    ):
        await phile.launcher.defaults.add(
            capability_registry=capability_registry,
        )
        return await async_target(capability_registry)


def run(async_target: AsyncTarget[_T]) -> _T:  # pragma: no cover
    capability_registry = phile.capability.Registry()
    with phile.capability.asyncio.provide_loop(
        capability_registry=capability_registry,
    ) as loop:
        main_task = loop.create_task(
            _async_run(
                async_target=async_target,
                capability_registry=capability_registry,
            ),
        )
        main_task.add_done_callback(lambda _task: loop.stop())
        loop.run_forever()
        if not main_task.done():
            asyncio.set_event_loop(None)
            launcher_registry = (
                capability_registry[phile.launcher.Registry]
            )
            # pylint: disable=protected-access
            if 'pyside2' in launcher_registry.state_machine._start_tasks:
                # pylint: disable=import-outside-toplevel
                import PySide2.QtWidgets
                qt_app = PySide2.QtWidgets.QApplication()
                qt_app.aboutToQuit.connect(
                    functools.partial(
                        loop.call_soon_threadsafe,
                        launcher_registry.state_machine.stop_soon,
                        'pyside2',
                    )
                )
                asyncio_thread = threading.Thread(
                    target=loop.run_forever
                )
                asyncio_thread.start()
                qt_app.exec_()
                asyncio_thread.join()
            else:
                # Cannot determine why the loop was stopped.
                # Cancel and clean up.
                main_task.cancel()
                loop.run_until_complete(main_task)
        return main_task.result()
