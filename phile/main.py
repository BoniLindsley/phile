#!/usr/bin/env python3

# Standard library.
import asyncio
import collections.abc
import dataclasses
import functools
import logging
import threading
import typing

# Internal packages.
import phile.launcher
import phile.launcher.defaults

_T = typing.TypeVar("_T")
AsyncTarget = collections.abc.Callable[
    [phile.launcher.Registry], collections.abc.Awaitable[_T]
]

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)


@dataclasses.dataclass
class _InverseDependencyData(typing.Generic[_T]):
    async_target: AsyncTarget[_T]
    launcher_registry: typing.Optional[phile.launcher.Registry] = None


async def _async_run(data: _InverseDependencyData[_T]) -> _T:
    launcher_registry = phile.launcher.Registry()
    try:
        phile.launcher.defaults.add(launcher_registry=launcher_registry)
        data.launcher_registry = launcher_registry
        _logger.debug("Target of asyncio loop is starting.")
        try:
            return await data.async_target(launcher_registry)
        finally:
            _logger.debug("Target of asyncio loop has stopped.")
    finally:
        await launcher_registry.start("phile_shutdown.target")


def run(async_target: AsyncTarget[_T]) -> _T:
    loop = asyncio.new_event_loop()
    # This statement should technically be wrapped in a try block
    # that closes the loop on any exception.
    # But this is such a basic building block that, if it breaks,
    # then we might as well just terminate.
    asyncio.set_event_loop(loop)
    try:
        data = _InverseDependencyData(async_target=async_target)
        main_task = loop.create_task(_async_run(data=data))
        main_task.add_done_callback(lambda _task: loop.stop())
        loop.run_forever()
        if not main_task.done():
            asyncio.set_event_loop(None)
            launcher_registry = data.launcher_registry
            # pylint: disable=protected-access
            if (launcher_registry is not None) and (
                "pyside2" in launcher_registry.state_machine._start_tasks
            ):
                # pylint: disable=import-outside-toplevel
                import PySide2.QtWidgets

                qt_app = PySide2.QtWidgets.QApplication()
                qt_app.aboutToQuit.connect(
                    functools.partial(
                        loop.call_soon_threadsafe,
                        launcher_registry.state_machine.stop,
                        "pyside2",
                    )
                )
                qt_app.setQuitLockEnabled(False)
                loop.call_soon_threadsafe(
                    main_task.add_done_callback,
                    (lambda _task: qt_app.quit()),
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
    finally:
        asyncio.set_event_loop(loop)
        phile.asyncio.close()
