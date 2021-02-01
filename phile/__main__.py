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
import phile.tray.publishers.battery
import phile.tray.publishers.datetime
import phile.tray.publishers.memory
import phile.tray.publishers.network
import phile.tray.publishers.notify_monitor
import phile.tray.publishers.update
import phile.trigger
import phile.watchdog

Launcher = typing.Callable[[phile.Capabilities], typing.Coroutine]

default_launchers: typing.Dict[str, Launcher] = {
    'tray-battery': phile.tray.publishers.battery.run,
    'tray-datetime': phile.tray.publishers.datetime.run,
    'tray-memory': phile.tray.publishers.memory.run,
    'tray-network': phile.tray.publishers.network.run,
    'tray-notify': phile.tray.publishers.notify_monitor.run,
}


@dataclasses.dataclass
class TaskRegistry:
    """Keeps track of existing tasks and how to start new tasks."""

    capabilities: phile.Capabilities
    launchers: types.MappingProxyType[
        str, Launcher] = types.MappingProxyType(default_launchers)

    def __post_init__(self) -> None:
        self.running_tasks: dict[str, asyncio.Task[typing.Any]] = {}

    def create_task(self, name: str) -> asyncio.Task[typing.Any]:
        assert name not in self.running_tasks
        self.running_tasks[name] = task = asyncio.create_task(
            self.launchers[name](self.capabilities), name=name
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
        self, *args: typing.Any, capabilities: phile.Capabilities,
        **kwargs: typing.Any
    ) -> None:
        super().__init__(
            *args,
            configuration=capabilities[phile.Configuration],
            **kwargs
        )
        self.task_registry = TaskRegistry(capabilities=capabilities)
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


async def run(capabilities: phile.Capabilities) -> None:
    loop = asyncio.get_running_loop()
    with TriggerEntryPoint(
        capabilities=capabilities,
        trigger_directory=pathlib.Path('phile')
    ) as entry_point, phile.watchdog.Scheduler(
        watched_path=entry_point.trigger_directory,
        watching_observer=capabilities[
            watchdog.observers.api.BaseObserver],
        path_filter=entry_point.check_path,
        path_handler=functools.partial(
            loop.call_soon_threadsafe, entry_point.activate_trigger
        )
    ):
        entry_point.add_all_triggers()
        while True:
            await asyncio.sleep(3600)


async def async_main(argv: typing.List[str]) -> int:  # pragma: no cover
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    async with phile.watchdog.observers.async_open() as observer:
        capabilities[watchdog.observers.api.BaseObserver] = observer
        await run(capabilities=capabilities)
    return 0


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
