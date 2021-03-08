#!/usr/bin/env python3

# Standard library.
import argparse
import asyncio
import collections.abc
import contextlib
import dataclasses
import functools
import importlib.util
import os
import platform
import subprocess
import sys
import threading
import types
import typing

# External dependencies.
import keyring
import watchdog.observers

# Internal packages.
import phile
import phile.asyncio
import phile.tray.publishers.battery
import phile.tray.publishers.cpu
import phile.tray.publishers.datetime
import phile.tray.publishers.imap_idle
import phile.tray.publishers.memory
import phile.tray.publishers.network
import phile.tray.publishers.notify_monitor
import phile.tray.publishers.update
import phile.tray.tmux
import phile.trigger
import phile.trigger.cli
import phile.watchdog

NullaryCallable = typing.Callable[[], typing.Any]
Launcher = typing.Callable[[phile.Capabilities], typing.Coroutine]
LauncherEntry = tuple[Launcher, set[type]]

default_launchers: typing.Dict[str, LauncherEntry] = {
    'imap-idle': (
        phile.tray.publishers.imap_idle.run,
        {
            phile.Configuration,
            keyring.backend.KeyringBackend,
        },
    ),
    'tray-battery':
        (phile.tray.publishers.battery.run, {
            phile.Configuration,
        }),
    'tray-cpu': (phile.tray.publishers.cpu.run, {
        phile.Configuration,
    }),
    'tray-datetime':
        (phile.tray.publishers.datetime.run, {
            phile.Configuration,
        }),
    'tray-memory':
        (phile.tray.publishers.memory.run, {
            phile.Configuration,
        }),
    'tray-network':
        (phile.tray.publishers.network.run, {
            phile.Configuration,
        }),
    'tray-notify': (
        phile.tray.publishers.notify_monitor.run,
        {
            phile.Configuration,
            watchdog.observers.api.BaseObserver,
        },
    ),
    'tray-tmux': (
        phile.tray.tmux.run,
        {
            phile.Configuration,
            phile.tmux.control_mode.Client,
            watchdog.observers.api.BaseObserver,
        },
    ),
}


@dataclasses.dataclass
class TaskRegistry:
    """Keeps track of existing tasks and how to start new tasks."""

    class MissingCapability(RuntimeError):
        pass

    capabilities: phile.Capabilities
    launchers: types.MappingProxyType[
        str, LauncherEntry] = types.MappingProxyType(default_launchers)

    def __post_init__(self) -> None:
        self.running_tasks: dict[str, asyncio.Task[typing.Any]] = {}
        capability_set = set(self.capabilities.keys())
        self.usable_launcher_names = {
            name
            for name, launcher_entry in self.launchers.items()
            if not launcher_entry[1].difference(capability_set)
        }

    def create_task(self, name: str) -> asyncio.Task[typing.Any]:
        assert name not in self.running_tasks
        launcher_entry = self.launchers[name]
        if name not in self.usable_launcher_names:
            required_launcher_capabilities = launcher_entry[1]
            missing_capabilities = (
                required_launcher_capabilities.difference(
                    self.capabilities
                )
            )
            raise TaskRegistry.MissingCapability(
                f"Launcher {name} requires {missing_capabilities}."
            )
        launcher = launcher_entry[0]
        self.running_tasks[name] = task = asyncio.create_task(
            launcher(self.capabilities), name=name
        )
        task.add_done_callback(self.on_task_done)
        return task

    def cancel_task(self, name: str) -> None:
        assert name in self.running_tasks
        self.running_tasks[name].cancel()

    def on_task_done(self, task: asyncio.Task[typing.Any]) -> None:
        self.running_tasks.pop(task.get_name())


class TriggerProvider(phile.trigger.Provider):
    """Provides triggers to start and stop tasks."""

    __Self = typing.TypeVar('__Self', bound='TriggerProvider')

    def __init__(
        self,
        *args: typing.Any,
        capabilities: phile.Capabilities,
        **kwargs: typing.Any,
    ) -> None:
        self._capabilities = capabilities
        self.start_prefix = 'start-task_'
        self.stop_prefix = 'stop-task_'
        self.task_registry = TaskRegistry(capabilities=capabilities)
        callbacks = self.get_triggers()
        trigger_registry = capabilities[phile.trigger.Registry]
        super().__init__(
            *args,
            callback_map=callbacks,
            registry=trigger_registry,
            **kwargs,
        )

    def __enter__(self: __Self) -> __Self:
        super().__enter__()
        for task_name in self.task_registry.usable_launcher_names:
            self.create_task(task_name)
        return self

    def get_triggers(self) -> dict[str, NullaryCallable]:
        callbacks: dict[str, NullaryCallable] = {}
        usable_launchers = {
            name: launcher
            for (name, launcher) in self.task_registry.launchers.items()
            if name in self.task_registry.usable_launcher_names
        }
        # TODO[mypy issue #4717]: Remove `ignore[misc]`.
        # Cannot use abstract class.
        loop = self._capabilities[
            asyncio.events.AbstractEventLoop  # type: ignore[misc]
        ]
        for task_name in usable_launchers:
            callbacks[self.start_prefix + task_name] = functools.partial(
                loop.call_soon_threadsafe,
                self.create_task,
                task_name,
            )
            callbacks[self.stop_prefix + task_name] = functools.partial(
                self.task_registry.cancel_task, task_name
            )
        return callbacks

    def create_task(self, task_name: str) -> asyncio.Task[typing.Any]:
        self.hide(self.start_prefix + task_name)
        self.show(self.stop_prefix + task_name)
        task = self.task_registry.create_task(name=task_name)
        task.add_done_callback(self.on_task_done)
        return task

    def on_task_done(self, task: asyncio.Task[typing.Any]) -> None:
        task_name = task.get_name()
        with contextlib.suppress(
            ResourceWarning, phile.trigger.Provider.NotBound
        ):
            self.hide(self.stop_prefix + task_name)
            self.show(self.start_prefix + task_name)


class CleanUps(phile.trigger.Provider):

    __Self = typing.TypeVar('__Self', bound='CleanUps')

    def __init__(
        self, *args: typing.Any, capabilities: phile.Capabilities,
        **kwargs: typing.Any
    ) -> None:
        self.callbacks = set[NullaryCallable]()
        registry = capabilities[phile.trigger.Registry]
        super().__init__(
            *args,
            callback_map={'quit': self.run},
            registry=registry,
            **kwargs
        )

    def __enter__(self: __Self) -> __Self:
        super().__enter__()
        self.show_all()
        return self

    def run(self) -> None:
        for callback in self.callbacks.copy():
            callback()

    @contextlib.contextmanager
    def open(
        self, callback: NullaryCallable
    ) -> collections.abc.Iterator[None]:
        try:
            self.callbacks.add(callback)
            yield
        finally:
            self.callbacks.discard(callback)


_T_co = typing.TypeVar('_T_co', covariant=True)


async def open_prompt(capabilities: phile.Capabilities) -> None:
    # TODO[mypy issue #4717]: Remove `ignore[misc]`.
    # Cannot use abstract class.
    loop = capabilities[asyncio.AbstractEventLoop]  # type: ignore[misc]
    prompt = phile.trigger.cli.Prompt(capabilities=capabilities)
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(
        functools.partial(asyncio.StreamReaderProtocol, reader),
        prompt.stdin
    )
    writer = asyncio.StreamWriter(
        *(
            await loop.connect_write_pipe(
                asyncio.streams.FlowControlMixin, prompt.stdout
            )
        ), reader, loop
    )
    if prompt.intro:
        writer.write(prompt.intro)
    is_stopping = False
    while not is_stopping:
        writer.write(prompt.prompt.encode())
        next_command = await reader.readline()
        is_stopping = prompt.onecmd(next_command.decode())


async def run(capabilities: phile.Capabilities) -> int:
    with TriggerProvider(capabilities=capabilities):
        await open_prompt(capabilities=capabilities)
    return 0


async def async_main(capabilities: phile.Capabilities) -> int:
    clean_ups = capabilities[CleanUps]
    loop = asyncio.get_running_loop()
    AbstractEventLoop = (  # pylint: disable=invalid-name
            asyncio.events.AbstractEventLoop
    )
    # TODO[mypy issue #4717]: Remove `ignore[misc]`.
    # Cannot use abstract class.
    capabilities[AbstractEventLoop] = loop  # type: ignore[misc]

    async with contextlib.AsyncExitStack() as stack:
        stack.enter_context(contextlib.suppress(asyncio.CancelledError))

        if 'TMUX' in os.environ:
            control_mode = await stack.enter_async_context(
                phile.tmux.control_mode.open(
                    control_mode_arguments=(
                        phile.tmux.control_mode.Arguments()
                    )
                )
            )
            capabilities[phile.tmux.control_mode.Client] = control_mode
            await stack.enter_async_context(
                phile.asyncio.open_task(control_mode.run())
            )
        await stack.enter_async_context(
            phile.asyncio.open_task(run(capabilities=capabilities))
        )
        quit_event = asyncio.Event()
        stack.enter_context(
            clean_ups.open(
                functools.partial(
                    loop.call_soon_threadsafe, quit_event.set
                )
            )
        )
        await quit_event.wait()
    del capabilities[AbstractEventLoop]
    return 0


def is_gui_available() -> bool:
    if platform.system() == 'Windows':
        return True
    try:
        subprocess.run(
            ['xset', 'q'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError:
        return False
    return True


def is_pyside2_available() -> bool:
    return importlib.util.find_spec('PySide2') is not None


def import_pyside2_qtwidgets() -> None:
    # pylint: disable=import-outside-toplevel
    # pylint: disable=invalid-name
    # pylint: disable=redefined-outer-name
    # pylint: disable=unused-import
    global PySide2
    global phile
    import PySide2.QtWidgets
    import phile.PySide2


def create_and_exec_qapplication(
    capabilities: phile.Capabilities
) -> None:
    clean_ups = capabilities[CleanUps]
    import_pyside2_qtwidgets()
    qt_app = (
        # pylint: disable=undefined-variable
        PySide2.QtWidgets.QApplication()  # type: ignore[name-defined]
    )
    capabilities.set(qt_app)
    with clean_ups.open(
        functools.partial(
            phile.PySide2.call_soon_threadsafe, qt_app.quit
        )
    ):
        qt_app.exec_()
    del capabilities[
        # pylint: disable=undefined-variable
        PySide2.QtWidgets.QApplication  # type: ignore[name-defined]
    ]
    del qt_app


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    with contextlib.ExitStack() as stack:
        stack.enter_context(contextlib.suppress(KeyboardInterrupt))

        if argv is None:
            argv = sys.argv
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '--gui', action=argparse.BooleanOptionalAction
        )
        args = parser.parse_args(argv[1:])

        capabilities = phile.Capabilities()
        capabilities.set(phile.Configuration())

        registry = phile.trigger.Registry()
        capabilities.set(registry)

        capabilities.set(
            stack.enter_context(CleanUps(capabilities=capabilities))
        )

        BaseObserver = watchdog.observers.api.BaseObserver
        capabilities[BaseObserver] = (
            stack.enter_context(phile.watchdog.observers.open())
        )
        stack.enter_context(
            phile.trigger.watchdog.View(capabilities=capabilities)
        )
        KeyringBackend = keyring.backend.KeyringBackend
        # TODO[mypy issue #4717]: Remove `ignore[misc]`.
        # Cannot use abstract class.
        capabilities[KeyringBackend] = (  # type: ignore[misc]
            # Don't reformat -- causes linebreak at [ ].
            keyring.get_keyring()
        )

        if args.gui or (
            args.gui is None and is_gui_available()
            and is_pyside2_available()
        ):
            non_gui_loop_thread = threading.Thread(
                target=functools.
                partial(asyncio.run, async_main(capabilities))
            )
            non_gui_loop_thread.start()

            create_and_exec_qapplication(capabilities)

            registry.activate_if_shown('quit')
            non_gui_loop_thread.join()
        else:
            asyncio.run(async_main(capabilities))
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
