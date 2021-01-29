#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import dataclasses
import functools
import pathlib
import sys
import types
import typing

# External dependencies.
import watchdog.observers

# Internal packages.
import phile
import phile
import phile.tray.publishers.battery
import phile.tray.publishers.datetime
import phile.tray.publishers.memory
import phile.tray.publishers.network
import phile.tray.publishers.notify_monitor
import phile.tray.publishers.update
import phile.trigger
import phile.watchdog


class Context(phile.Configuration):

    def __init__(
        self, *args: typing.Any,
        watching_observer: watchdog.observers.api.BaseObserver,
        **kwargs: typing.Any
    ):
        super().__init__(*args, **kwargs)
        self.watching_observer = watching_observer

    def __enter__(self) -> 'Context':
        self.watching_observer.start()
        return self

    def __exit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> typing.Optional[bool]:
        self.watching_observer.stop()
        return None


Launcher = typing.Callable[[Context], typing.Coroutine]

default_launchers: typing.Dict[str, Launcher] = {
    'tray-battery':
        lambda context: phile.tray.publishers.update.sleep_loop(
            phile.tray.publishers.battery.
            TrayFilesUpdater(configuration=context)
        ),
    'tray-datetime':
        lambda context: phile.tray.publishers.update.sleep_loop(
            phile.tray.publishers.datetime.
            TrayFilesUpdater(configuration=context)
        ),
    'tray-memory':
        lambda context: phile.tray.publishers.update.sleep_loop(
            phile.tray.publishers.memory.
            TrayFilesUpdater(configuration=context)
        ),
    'tray-network':
        lambda context: phile.tray.publishers.update.sleep_loop(
            phile.tray.publishers.network.
            TrayFilesUpdater(configuration=context)
        ),
    'tray-notify':
        lambda context: phile.tray.publishers.notify_monitor.monitor(
            configuration=context,
            watching_observer=context.watching_observer
        )
}


@dataclasses.dataclass
class TaskRegistry:
    """Keeps track of existing tasks and how to start new tasks."""

    context: Context
    launchers: types.MappingProxyType[
        str, Launcher] = types.MappingProxyType(default_launchers)

    def __post_init__(self) -> None:
        self.running_tasks: dict[str, asyncio.Task[typing.Any]] = {}

    def create_task(self, name: str) -> asyncio.Task[typing.Any]:
        assert name not in self.running_tasks
        self.running_tasks[name] = task = asyncio.create_task(
            self.launchers[name](self.context), name=name
        )
        task.add_done_callback(self.on_task_done)
        return task

    def cancel_task(self, name: str) -> None:
        assert name in self.running_tasks
        self.running_tasks[name].cancel()

    def on_task_done(self, task: asyncio.Task[typing.Any]) -> None:
        self.running_tasks.pop(task.get_name())


class TriggerEntryPoint(phile.trigger.EntryPoint):
    """Provides triggers to start and stop tasks."""

    def __init__(
        self, *args: typing.Any, context: Context, **kwargs: typing.Any
    ) -> None:
        super().__init__(*args, configuration=context, **kwargs)
        self.task_registry = TaskRegistry(context=context)
        self.start_prefix = 'start-task_'
        self.stop_prefix = 'stop-task_'

    def __enter__(self) -> 'TriggerEntryPoint':
        super().__enter__()
        return self

    def add_all_triggers(self) -> None:
        for task_name in self.task_registry.launchers:
            self.callback_map[self.start_prefix + task_name] = (
                functools.partial(self.create_task, task_name)
            )
            self.callback_map[self.stop_prefix + task_name] = (
                functools.partial(
                    self.task_registry.cancel_task, task_name
                )
            )
            self.add_trigger(self.start_prefix + task_name)

    def create_task(self, task_name: str) -> asyncio.Task[typing.Any]:
        self.remove_trigger(self.start_prefix + task_name)
        self.add_trigger(self.stop_prefix + task_name)
        task = self.task_registry.create_task(name=task_name)
        task.add_done_callback(self.on_task_done)
        return task

    def on_task_done(self, task: asyncio.Task[typing.Any]) -> None:
        task_name = task.get_name()
        with contextlib.suppress(ResourceWarning):
            self.remove_trigger(self.stop_prefix + task_name)
            self.add_trigger(self.start_prefix + task_name)


async def run(context: Context) -> None:
    loop = asyncio.get_running_loop()
    with TriggerEntryPoint(
        context=context, trigger_directory=pathlib.Path('phile')
    ) as entry_point, phile.watchdog.Scheduler(
        watched_path=entry_point.trigger_directory,
        watching_observer=context.watching_observer,
        path_filter=entry_point.check_path,
        path_handler=functools.partial(
            loop.call_soon_threadsafe, entry_point.activate_trigger
        )
    ):
        entry_point.add_all_triggers()
        while True:
            await asyncio.sleep(3600)


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    with Context(watching_observer=watchdog.observers.Observer()
                 ) as context, contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(context=context))
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
