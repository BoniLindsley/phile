#!/usr/bin/env python3
"""
.. automodule:: phile.launcher.cmd
.. automodule:: phile.launcher.defaults

----------------------------------
For starting and stopping services
----------------------------------
"""

# Standard libraries.
import asyncio
import collections
import collections.abc
import contextlib
import dataclasses
import enum
import functools
import types
import typing

# Internal modules.
import phile
import phile.capability
import phile.pubsub_event

Awaitable = collections.abc.Awaitable[typing.Any]
NullaryAsyncCallable = collections.abc.Callable[[], Awaitable]
NullaryCallable = collections.abc.Callable[[], typing.Any]
Command = NullaryAsyncCallable
CommandLines = list[Command]


class Type(enum.IntEnum):
    """
    Determines how to start and stop a :class:`Descriptor`.

    This controls what to call in order to start a unit,
    and the conditions sufficient to determine that
    the unit has successfully started.
    When a unit has started successfully,
    units that depends on it being started successfully
    may then also start if it requested to be started.
    That is, the conditions should reflect
    whether the unit is ready to perform external requests.

    This also controls the coroutine to be identified
    as the main subroutine of the unit.
    When the main subroutine returns, after being cancelled or otherwise,
    the unit is considered to have stopped.
    """
    SIMPLE = enum.auto()
    """
    A simple :class:`Descriptor` startes
    when its :attr:`~Descriptor.exec_start` coroutine is scheduled.

    In this context, a coroutine is considered scheduled
    if it is queued in the event loop to be ran soon,
    and the coroutine is not necessary given control at any point.
    This behaviour matters if the coroutine is cancelled
    before it is given a chance to run.
    However, in practice, because of implementation detail,
    the coroutine is always given a chance to run at least once.
    """
    EXEC = enum.auto()
    """
    An exec :class:`Descriptor` startes
    when its :attr:`~Descriptor.exec_start` coroutine starts.

    In this context, a coroutine is considered started
    when its routine is given a chance to ran,
    and has yielded control back to the event loop.
    """
    FORKING = enum.auto()
    """
    A forking :class:`Descriptor` starts
    when its :attr:`~Descriptor.exec_start` coroutine returns.

    A forking unit must return an :class:`asyncio.Future`
    from its ``exec_start`` coroutine.
    The future is then identified s the main subroutine of the unit.
    """


class Descriptor(typing.TypedDict, total=False):
    after: set[str]
    binds_to: set[str]
    exec_start: CommandLines
    exec_stop: CommandLines
    type: Type


class MissingDescriptorData(KeyError):
    pass


class NameInUse(RuntimeError):
    pass


class Database:

    @dataclasses.dataclass
    class Event:
        source: 'Database'
        type: collections.abc.Callable[..., typing.Any]
        entry_name: str

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.event_publisher = (
            phile.pubsub_event.Publisher[Database.Event]()
        )
        """Pushes events to subscribers."""
        self.known_descriptors: dict[str, Descriptor] = {}
        """
        The launcher names added, with given :class:`Descriptor`.

        The descriptors added are stored as given
        for debugging purposes only.
        In particular, if the descriptors given are subsequently changed,
        the stored description would be changed as well,
        but associated launcher behaviour would not be.
        (That may be achieved by removing and adding again,
        but that would likely stop all dependents.)
        Therefore, the data is parsed when adding as necessary,
        and should not be relied upon afterwards.
        """
        self.after: dict[str, set[str]] = {}
        """Order dependencies of launchers."""
        self.binds_to: dict[str, set[str]] = {}
        """Dependencies of launchers."""
        self.exec_start: dict[str, CommandLines] = {}
        """Coroutines to call to start a launcher."""
        self.exec_stop: dict[str, CommandLines] = {}
        """Coroutines to call to stop a launcher."""
        self.remover: dict[str, NullaryCallable] = {}
        """Callback to call to remove launchers from the database."""
        self.type: dict[str, Type] = {}
        """Initialisation and termination conditions of launchers."""
        # The data after this are not given in descriptors,
        # but derived from them.
        self.bound_by: dict[str, set[str]] = {}
        """Dependents of launchers."""
        self.stop_after: dict[str, set[str]] = {}
        """Order dependencies for stopping launchers."""

    def add(self, entry_name: str, descriptor: Descriptor) -> None:
        """Not thread-safe."""
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                self._update_descriptor(entry_name, descriptor)
            )
            stack.enter_context(self._update_after(entry_name))
            stack.enter_context(self._update_type(entry_name))
            stack.enter_context(self._update_exec_start(entry_name))
            stack.enter_context(self._update_exec_stop(entry_name))
            stack.enter_context(self._update_binds_to(entry_name))
            stack.enter_context(self._update_events(entry_name))
            self.remover[entry_name] = functools.partial(
                stack.pop_all().__exit__, None, None, None
            )

    @contextlib.contextmanager
    def _update_descriptor(
        self, entry_name: str, descriptor: Descriptor
    ) -> collections.abc.Iterator[None]:
        known_descriptors = self.known_descriptors
        if entry_name in known_descriptors:
            raise NameInUse(
                'Launchers cannot be added with the same name.'
                ' The following given name is already in use:'
                ' {entry_name}'.format(entry_name=entry_name)
            )
        try:
            known_descriptors[entry_name] = descriptor
            yield
        finally:
            known_descriptors.pop(entry_name, None)

    @contextlib.contextmanager
    def _update_after(
        self,
        entry_name: str,
    ) -> collections.abc.Iterator[None]:
        descriptor = self.known_descriptors[entry_name]
        descriptor_after = descriptor.get('after', set())
        entry_after = set[str]()
        after = self.after
        try:
            after[entry_name] = entry_after
            stop_after = self.stop_after
            try:
                for dependency in descriptor_after:
                    entry_after.add(dependency)
                    dependency_stop_after = stop_after.setdefault(
                        dependency, set[str]()
                    )
                    dependency_stop_after.add(entry_name)
                    del dependency_stop_after
                del descriptor_after
                yield
            finally:
                for dependency in entry_after:
                    dependency_stop_after = stop_after.get(
                        dependency, set[str]()
                    )
                    dependency_stop_after.discard(entry_name)
                    if not dependency_stop_after:
                        stop_after.pop(dependency, None)
                    del dependency_stop_after
        finally:
            after.pop(entry_name, None)

    @contextlib.contextmanager
    def _update_type(
        self,
        entry_name: str,
    ) -> collections.abc.Iterator[None]:
        type_dict = self.type
        descriptor = self.known_descriptors[entry_name]
        try:
            type_dict[entry_name] = descriptor.get('type', Type.SIMPLE)
            yield
        finally:
            type_dict.pop(entry_name, None)

    @contextlib.contextmanager
    def _update_exec_start(
        self,
        entry_name: str,
    ) -> collections.abc.Iterator[None]:
        exec_start = self.exec_start
        descriptor = self.known_descriptors[entry_name]
        try:
            try:
                new_exec_start = descriptor['exec_start']
            except KeyError as error:
                raise MissingDescriptorData(
                    'A launcher.Descriptor must provide'
                    ' a exec_start coroutine to be added.'
                    ' It is missing from the unit named'
                    ' {entry_name}'.format(entry_name=entry_name)
                ) from error
            exec_start[entry_name] = new_exec_start
            yield
        finally:
            exec_start.pop(entry_name, None)

    @contextlib.contextmanager
    def _update_exec_stop(
        self,
        entry_name: str,
    ) -> collections.abc.Iterator[None]:
        exec_stop = self.exec_stop
        descriptor = self.known_descriptors[entry_name]
        try:
            exec_stop[entry_name] = descriptor.get('exec_stop', [])
            yield
        finally:
            exec_stop.pop(entry_name, None)

    @contextlib.contextmanager
    def _update_binds_to(
        self,
        entry_name: str,
    ) -> collections.abc.Iterator[None]:
        descriptor = self.known_descriptors[entry_name]
        descriptor_binds_to = descriptor.get('binds_to', set())
        entry_binds_to = set[str]()
        binds_to = self.binds_to
        try:
            binds_to[entry_name] = entry_binds_to
            bound_by = self.bound_by
            try:
                for bind_target in descriptor_binds_to:
                    entry_binds_to.add(bind_target)
                    target_bound_by = bound_by.setdefault(
                        bind_target, set[str]()
                    )
                    target_bound_by.add(entry_name)
                    del target_bound_by
                del descriptor_binds_to
                yield
            finally:
                for bind_target in entry_binds_to:
                    target_bound_by = bound_by.get(
                        bind_target, set[str]()
                    )
                    target_bound_by.discard(entry_name)
                    if not target_bound_by:
                        bound_by.pop(bind_target, None)
                    del target_bound_by
        finally:
            binds_to.pop(entry_name, None)

    @contextlib.contextmanager
    def _update_events(
        self,
        entry_name: str,
    ) -> collections.abc.Iterator[None]:
        self.event_publisher.push(
            self.Event(
                source=self,
                type=Database.add,
                entry_name=entry_name,
            )
        )
        try:
            yield
        finally:
            try:
                self.event_publisher.push(
                    self.Event(
                        source=self,
                        type=Database.remove,
                        entry_name=entry_name,
                    )
                )
            except RuntimeError:  # pragma: no cover  # Defensive.
                # If there is no current event loop,
                # pushing is not possible, and asyncio raises this.
                pass

    def remove(self, entry_name: str) -> None:
        entry_remover = self.remover.pop(entry_name, None)
        if entry_remover is not None:
            entry_remover()

    def contains(self, entry_name: str) -> bool:
        return entry_name in self.remover


class StateMachine:

    @dataclasses.dataclass
    class Event:
        source: 'StateMachine'
        type: collections.abc.Callable[..., typing.Any]
        entry_name: str

    def __init__(
        self, *args: typing.Any, database: Database, **kwargs: typing.Any
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.event_publisher = (
            phile.pubsub_event.Publisher[StateMachine.Event]()
        )
        """Pushes events to subscribers."""
        self._database = database
        self._running_tasks: dict[str, asyncio.Future[typing.Any]] = {}
        self._start_tasks: dict[str, asyncio.Future[typing.Any]] = {}
        self._stop_tasks: dict[str, asyncio.Future[typing.Any]] = {}

    async def start(self, entry_name: str) -> None:
        await self._get_start_task(entry_name)

    def start_soon(self, entry_name: str) -> asyncio.Future[typing.Any]:
        return self._get_start_task(entry_name)

    def _get_start_task(
        self,
        entry_name: str,
    ) -> asyncio.Future[typing.Any]:
        start_tasks = self._start_tasks
        try:
            entry_start_task = start_tasks[entry_name]
        except KeyError:
            entry_start_task = start_tasks[entry_name] = (
                asyncio.create_task(self._ensure_started(entry_name))
            )
            entry_start_task.add_done_callback(
                functools.partial(start_tasks.pop, entry_name)
            )
        return entry_start_task

    async def _ensure_started(self, entry_name: str) -> None:
        # If a launcher is started while it is being stopped,
        # assume a restart-like behaviour is desired.
        # So wait till the launcher has stopped before starting.
        entry_stop_task = self._stop_tasks.get(entry_name)
        if entry_stop_task is not None:
            await entry_stop_task
        running_tasks = self._running_tasks
        if entry_name in running_tasks:
            return
        ready_event = asyncio.Event()
        ready_task = asyncio.create_task(ready_event.wait())
        entry_task = running_tasks[entry_name] = asyncio.create_task(
            self._run(entry_name, ready_event)
        )
        entry_task.add_done_callback(
            functools.partial(running_tasks.pop, entry_name)
        )
        done, _pending = await asyncio.wait(
            (ready_task, entry_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if ready_task.cancel():
            with contextlib.suppress(asyncio.CancelledError):
                await ready_task
        if ready_task not in done:
            # Launcher did not start successfully.
            # Propagate error by awaiting on it.
            await entry_task

    async def stop(self, entry_name: str) -> None:
        await self._get_stop_task(entry_name)

    def stop_soon(self, entry_name: str) -> asyncio.Future[typing.Any]:
        return self._get_stop_task(entry_name)

    def _get_stop_task(
        self,
        entry_name: str,
    ) -> asyncio.Future[typing.Any]:
        stop_tasks = self._stop_tasks
        try:
            entry_stop_task = stop_tasks[entry_name]
        except KeyError:
            entry_stop_task = stop_tasks[entry_name] = (
                asyncio.create_task(self._ensure_stopped(entry_name))
            )
            entry_stop_task.add_done_callback(
                functools.partial(stop_tasks.pop, entry_name)
            )
        return entry_stop_task

    async def _ensure_stopped(self, entry_name: str) -> None:
        entry_start_task = self._start_tasks.get(entry_name)
        if entry_start_task is not None and entry_start_task.cancel():
            with contextlib.suppress(asyncio.CancelledError):
                await entry_start_task
            return
        del entry_start_task

        entry_running_task = self._running_tasks.get(entry_name)
        if entry_running_task is not None and entry_running_task.cancel(
        ):
            with contextlib.suppress(asyncio.CancelledError):
                await entry_running_task

    async def _run(
        self,
        entry_name: str,
        ready_event: asyncio.Event,
    ) -> None:
        await self._start_dependencies(entry_name)
        await self._ensure_dependencies_are_started(entry_name)
        async with contextlib.AsyncExitStack() as stack:
            # When unwinding the stack,
            # emit event only when the task is assumed to be done.
            event_stack = await stack.enter_async_context(
                contextlib.AsyncExitStack()
            )
            main_task = await stack.enter_async_context(
                self._create_main_task(entry_name)
            )
            stack.push_async_callback(
                self._run_command_lines,
                self._database.exec_stop[entry_name],
            )
            stack.push_async_callback(
                self._ensure_dependents_are_stopped, entry_name
            )
            stack.push_async_callback(self._stop_dependents, entry_name)
            # When setting up,
            # emit event only when all clean-up is set up.
            event_stack.enter_context(self._update_events(entry_name))
            ready_event.set()
            await asyncio.shield(main_task)

    async def _start_dependencies(self, entry_name: str) -> None:
        for dependency_name in self._database.binds_to[entry_name]:
            self._get_start_task(dependency_name)

    async def _stop_dependents(self, entry_name: str) -> None:
        # Unlike bind_by entries, the bound_by entries
        # are not provided by descriptors.
        # So they are generated as dependencies are found.
        # In particular, there need not be a bound_by entry
        # if there are no dependencies for a particular launcher.
        try:
            entry_bound_by = self._database.bound_by[entry_name]
        except KeyError:
            return
        for dependent_name in entry_bound_by:
            self._get_stop_task(dependent_name)

    async def _ensure_dependencies_are_started(
        self, entry_name: str
    ) -> None:
        start_tasks = self._start_tasks
        after_tasks = (
            start_tasks.get(dependency_name)
            for dependency_name in self._database.after[entry_name]
        )
        order_dependency_tasks = tuple(
            tasks for tasks in after_tasks if tasks is not None
        )
        if order_dependency_tasks:
            await asyncio.wait(order_dependency_tasks)

    async def _ensure_dependents_are_stopped(
        self, entry_name: str
    ) -> None:
        stop_after = self._database.stop_after
        try:
            entry_stop_after = stop_after[entry_name]
        except KeyError:
            return
        stop_tasks = self._stop_tasks
        after_tasks = (
            stop_tasks.get(dependency_name)
            for dependency_name in entry_stop_after
        )
        order_dependency_tasks = tuple(
            tasks for tasks in after_tasks if tasks is not None
        )
        if order_dependency_tasks:
            await asyncio.wait(order_dependency_tasks)

    @contextlib.asynccontextmanager
    async def _create_main_task(
        self, entry_name: str
    ) -> collections.abc.AsyncIterator[asyncio.Future[typing.Any]]:
        database = self._database
        main_task: asyncio.Future[typing.Any] = asyncio.create_task(
            self._run_command_lines(database.exec_start[entry_name])
        )
        try:
            unit_type = database.type[entry_name]
            if unit_type is Type.EXEC:
                await asyncio.sleep(0)
            elif unit_type is Type.FORKING:
                main_task = await main_task
                assert isinstance(main_task, asyncio.Future)
            del unit_type
            yield main_task
        finally:
            if main_task.cancel():
                with contextlib.suppress(asyncio.CancelledError):
                    await main_task

    async def _run_command_lines(
        self, command_lines: CommandLines
    ) -> typing.Any:
        """Await the given command lines and return the last result."""
        return_value: typing.Any = None
        for command in command_lines:
            return_value = await command()
        return return_value

    def is_running(self, entry_name: str) -> bool:
        return entry_name in self._running_tasks

    @contextlib.contextmanager
    def _update_events(
        self,
        entry_name: str,
    ) -> collections.abc.Iterator[None]:
        self.event_publisher.push(
            self.Event(
                source=self,
                type=StateMachine.start,
                entry_name=entry_name,
            )
        )
        try:
            yield
        finally:
            try:
                self.event_publisher.push(
                    self.Event(
                        source=self,
                        type=StateMachine.stop,
                        entry_name=entry_name,
                    )
                )
            except RuntimeError:  # pragma: no cover  # Defensive.
                # If there is no current event loop,
                # pushing is not possible, and asyncio raises this.
                pass


class Registry:

    @dataclasses.dataclass
    class Event:
        source: 'Registry'
        type: collections.abc.Callable[..., typing.Any]
        entry_name: str

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.event_publisher = (
            phile.pubsub_event.Publisher[Registry.Event]()
        )
        self._database = database = Database()
        self._state_machine = StateMachine(database=database)
        self._event_forwarding_tasks = (
            asyncio.create_task(self._forward_database_events()),
            asyncio.create_task(self._forward_state_machine_events()),
        )

    @property
    def database(self) -> Database:
        return self._database

    @property
    def state_machine(self) -> StateMachine:
        return self._state_machine

    def register(self, entry_name: str, descriptor: Descriptor) -> None:
        self._database.add(entry_name, descriptor)

    async def deregister(self, entry_name: str) -> None:
        # No defensive mechanism to ensure it is not started again.
        # This is done in a best effort basis.
        await self.stop(entry_name)
        self._database.remove(entry_name)

    def is_registered(self, entry_name: str) -> bool:
        return self._database.contains(entry_name)

    async def start(self, entry_name: str) -> None:
        await self._state_machine.start(entry_name)

    async def stop(self, entry_name: str) -> None:
        await self._state_machine.stop(entry_name)

    def is_running(self, entry_name: str) -> bool:
        return self._state_machine.is_running(entry_name)

    async def _forward_database_events(self) -> None:
        subscriber = phile.pubsub_event.Subscriber[Database.Event](
            publisher=self._database.event_publisher
        )
        while event := await subscriber.pull():
            if event.type == Database.add:
                self.event_publisher.push(
                    self.Event(
                        source=self,
                        type=Registry.register,
                        entry_name=event.entry_name,
                    )
                )
            elif event.type == Database.remove:
                self.event_publisher.push(
                    self.Event(
                        source=self,
                        type=Registry.deregister,
                        entry_name=event.entry_name,
                    )
                )
            else:  # pragma: no cover  # Defensive.
                assert True, 'Unexpected event'

    async def _forward_state_machine_events(self) -> None:
        subscriber = phile.pubsub_event.Subscriber[StateMachine.Event](
            publisher=self._state_machine.event_publisher
        )
        while event := await subscriber.pull():
            if event.type == StateMachine.start:
                self.event_publisher.push(
                    self.Event(
                        source=self,
                        type=Registry.start,
                        entry_name=event.entry_name,
                    )
                )
            elif event.type == StateMachine.stop:
                self.event_publisher.push(
                    self.Event(
                        source=self,
                        type=Registry.stop,
                        entry_name=event.entry_name,
                    )
                )
            else:  # pragma: no cover  # Defensive.
                assert True, 'Unexpected event'


@contextlib.asynccontextmanager
async def provide_registry(
    capability_registry: phile.capability.Registry,
) -> collections.abc.AsyncIterator[Registry]:
    with capability_registry.provide(launcher_registry := Registry()):
        launcher_registry.database.add(
            launcher_name := 'phile.launcher',
            phile.launcher.Descriptor(exec_start=[asyncio.Event().wait])
        )
        await launcher_registry.state_machine.start(launcher_name)
        yield launcher_registry
        await launcher_registry.state_machine.stop(launcher_name)
