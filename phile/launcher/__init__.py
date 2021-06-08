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
import enum
import functools
import itertools
import logging
import types
import typing

# Internal modules.
import phile
import phile.asyncio
import phile.asyncio.pubsub
import phile.builtins
import phile.capability

_KeyT = typing.TypeVar('_KeyT')
_T = typing.TypeVar('_T')
_ValueT = typing.TypeVar('_ValueT')

Awaitable = collections.abc.Awaitable[typing.Any]
NullaryAsyncCallable = collections.abc.Callable[[], Awaitable]
NullaryCallable = collections.abc.Callable[[], typing.Any]
Command = NullaryAsyncCallable
CommandLines = list[Command]

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)


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
    before: set[str]
    binds_to: set[str]
    conflicts: set[str]
    default_dependencies: bool
    exec_start: CommandLines
    exec_stop: CommandLines
    type: Type


class MissingDescriptorData(KeyError):
    pass


class NameInUse(RuntimeError):
    pass


class OneToManyTwoWayDict(dict[_KeyT, set[_ValueT]]):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self._inverses = (
            collections.defaultdict[_ValueT, set[_KeyT]](set)
        )
        super().__init__(*args, **kwargs)

    def __setitem__(self, key: _KeyT, new_values: set[_ValueT]) -> None:
        if key in self:
            self.__delitem__(key)
        super().__setitem__(key, new_values)
        try:
            inverses = self._inverses
            for value in new_values:
                inverses[value].add(key)
        # Defensive. Not sure how to force this.
        # It should not happen in normal usage.
        except:  # pragma: no cover
            self.__delitem__(key)
            raise

    def __delitem__(self, key: _KeyT) -> None:
        try:
            inverses = self._inverses
            existing_values = self[key]
            for value in existing_values:
                inverse_set = inverses.get(value)
                # Defensive. Not sure how to force this.
                # It should not happen in normal usage.
                if inverse_set is not None:  # pragma: no branch
                    inverse_set.discard(key)
                    if not inverse_set:
                        inverses.pop(value, None)
                del inverse_set
        finally:
            super().__delitem__(key)

    @property
    def inverses(self) -> types.MappingProxyType[_ValueT, set[_KeyT]]:
        return types.MappingProxyType(self._inverses)

    @property
    def pop(self) -> None:  # type: ignore[override]
        # pylint: disable=invalid-overridden-method
        """Use ``del`` instead. Inverse bookeeping is done there."""
        raise AttributeError(
            "'OneToManyTwoWayDict' object has no attribute 'pop'"
        )


class Database:

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.event_publishers: (
            dict[collections.abc.Callable[..., typing.Any],
                 phile.asyncio.pubsub.Queue[str]]
        ) = {
            Database.add: phile.asyncio.pubsub.Queue[str](),
            Database.remove: phile.asyncio.pubsub.Queue[str](),
        }
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
        self.after = OneToManyTwoWayDict[str, str]()
        """Order dependencies of launchers."""
        self.before = OneToManyTwoWayDict[str, str]()
        """Order dependencies of launchers."""
        self.binds_to = OneToManyTwoWayDict[str, str]()
        """Dependencies of launchers."""
        self.conflicts = OneToManyTwoWayDict[str, str]()
        """Conflicts between launchers."""
        self.default_dependencies: dict[str, bool] = {}
        self.exec_start: dict[str, CommandLines] = {}
        """Coroutines to call to start a launcher."""
        self.exec_stop: dict[str, CommandLines] = {}
        """Coroutines to call to stop a launcher."""
        self.remover: dict[str, NullaryCallable] = {}
        """Callback to call to remove launchers from the database."""
        self.type: dict[str, Type] = {}
        """Initialisation and termination conditions of launchers."""

    async def add(self, entry_name: str, descriptor: Descriptor) -> None:
        """Not thread-safe."""
        self._check_new_descriptor(entry_name, descriptor)
        known_descriptors = self.known_descriptors
        # Not sure why Pylint thinks phile.builtins is a dict.
        provide_item = (
            phile.builtins.provide_item  # pylint: disable=no-member
        )
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                provide_item(known_descriptors, entry_name, descriptor)
            )

            def provide_option(option_name: str, default: _T) -> None:
                stack.enter_context(
                    provide_item(
                        getattr(self, option_name),
                        entry_name,
                        descriptor.get(option_name, default),
                    )
                )

            provide_option('after', set())
            provide_option('before', set())
            provide_option('binds_to', set[str]())
            provide_option('conflicts', set[str]())
            # Default value to be changed once it is implemented.
            provide_option('default_dependencies', False)
            provide_option('exec_start', None)
            provide_option('exec_stop', [])
            provide_option('type', Type.SIMPLE)
            if self.default_dependencies[entry_name]:
                self.before[entry_name].add('phile_shutdown.target')
                self.conflicts[entry_name].add('phile_shutdown.target')

            def publish_remove_event() -> None:
                publisher = self.event_publishers[Database.remove]
                try:
                    publisher.put(entry_name)
                except RuntimeError:  # pragma: no cover  # Defensive.
                    # If there is no current event loop,
                    # pushing is not possible, and asyncio raises this.
                    pass

            self.event_publishers[Database.add].put(entry_name)
            stack.callback(publish_remove_event)

            self.remover[entry_name] = functools.partial(
                stack.pop_all().__exit__, None, None, None
            )

    def _check_new_descriptor(
        self, entry_name: str, descriptor: Descriptor
    ) -> None:
        if entry_name in self.known_descriptors:
            raise NameInUse(
                'Launchers cannot be added with the same name.'
                ' The following given name is already in use:'
                ' {entry_name}'.format(entry_name=entry_name)
            )
        if 'exec_start' not in descriptor:
            raise MissingDescriptorData(
                'A launcher.Descriptor must provide'
                ' a exec_start coroutine to be added.'
                ' It is missing from the unit named'
                ' {entry_name}'.format(entry_name=entry_name)
            )

    async def remove(self, entry_name: str) -> None:
        entry_remover = self.remover.pop(entry_name, None)
        if entry_remover is not None:
            entry_remover()

    def contains(self, entry_name: str) -> bool:
        return entry_name in self.remover


class StateMachine:

    def __init__(
        self, *args: typing.Any, database: Database, **kwargs: typing.Any
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.event_publishers: (
            dict[collections.abc.Callable[..., typing.Any],
                 phile.asyncio.pubsub.Queue[str]]
        ) = {
            StateMachine.start: phile.asyncio.pubsub.Queue[str](),
            StateMachine.stop: phile.asyncio.pubsub.Queue[str](),
        }
        """Pushes events to subscribers."""
        self._database = database
        self._running_tasks: dict[str, asyncio.Future[typing.Any]] = {}
        self._start_tasks: dict[str, asyncio.Task[typing.Any]] = {}
        self._stop_tasks: dict[str, asyncio.Task[typing.Any]] = {}

    @property
    def database(self) -> Database:
        return self._database

    def start(
        self,
        entry_name: str,
    ) -> asyncio.Task[typing.Any]:
        start_tasks = self._start_tasks
        try:
            entry_start_task = start_tasks[entry_name]
        except KeyError:
            entry_start_task = start_tasks[entry_name] = (
                asyncio.create_task(self._do_start(entry_name))
            )
            entry_start_task.add_done_callback(
                functools.partial(start_tasks.pop, entry_name)
            )
        return entry_start_task

    def stop(
        self,
        entry_name: str,
    ) -> asyncio.Task[typing.Any]:
        stop_tasks = self._stop_tasks
        try:
            entry_stop_task = stop_tasks[entry_name]
        except KeyError:
            entry_stop_task = stop_tasks[entry_name] = (
                asyncio.create_task(self._do_stop(entry_name))
            )
            entry_stop_task.add_done_callback(
                functools.partial(stop_tasks.pop, entry_name)
            )
        return entry_stop_task

    async def _do_start(self, entry_name: str) -> None:
        # If a launcher is started while it is being stopped,
        # assume a restart-like behaviour is desired.
        # So wait till the launcher has stopped before starting.
        entry_stop_task = self._stop_tasks.get(entry_name)
        if entry_stop_task is not None:
            await entry_stop_task
        running_tasks = self._running_tasks
        if entry_name in running_tasks:
            return
        running_tasks = self._running_tasks
        await self._ensure_ready_to_start(entry_name)
        _logger.debug('Launcher %s is starting.', entry_name)
        main_task = await self._start_main_task(entry_name)
        _logger.debug('Launcher %s has started.', entry_name)
        running_tasks[entry_name] = runner_task = (
            asyncio.create_task(
                self._clean_up_on_stop(entry_name, main_task)
            )
        )
        runner_task.add_done_callback(
            functools.partial(running_tasks.pop, entry_name)
        )
        self.event_publishers[StateMachine.start].put(entry_name)
        runner_task.add_done_callback(
            lambda _task:
            (self.event_publishers[StateMachine.stop].put(entry_name))
        )

    async def _do_stop(self, entry_name: str) -> None:
        entry_start_task = self._start_tasks.get(entry_name)
        if entry_start_task is not None:
            await phile.asyncio.cancel_and_wait(entry_start_task)
        entry_running_task = self._running_tasks.get(entry_name)
        if entry_running_task is not None:
            await phile.asyncio.cancel_and_wait(entry_running_task)

    async def _clean_up_on_stop(
        self, entry_name: str, main_task: asyncio.Future[typing.Any]
    ) -> None:
        try:
            # A forced cancellation from this function
            # should not happen until dependents are processed
            # and a graceful shutdown is attempted.
            await asyncio.shield(main_task)
        finally:
            try:
                await self._ensure_ready_to_stop(entry_name)
            finally:
                try:
                    await self._run_command_lines(
                        self._database.exec_stop[entry_name]
                    )
                finally:
                    await phile.asyncio.cancel_and_wait(main_task)

    async def _ensure_ready_to_start(self, entry_name: str) -> None:
        database = self._database
        stop = self.stop
        _logger.debug('Launcher %s is stopping conflicts.', entry_name)
        for conflict in (
            database.conflicts.get(entry_name, set())
            | database.conflicts.inverses.get(entry_name, set())
        ):
            stop(conflict)
        _logger.debug(
            'Launcher %s is starting dependencies.', entry_name
        )
        start = self.start
        for dependency in database.binds_to[entry_name]:
            start(dependency)
        _logger.debug(
            'Launcher %s is waiting on dependencies.', entry_name
        )
        after = (
            database.after.get(entry_name, set())
            | database.before.inverses.get(entry_name, set())
        )
        before = (
            database.before.get(entry_name, set())
            | database.after.inverses.get(entry_name, set())
        )
        pending_tasks = set(
            filter(
                None,
                itertools.chain(
                    map(self._stop_tasks.get, after | before),
                    map(self._start_tasks.get, after),
                )
            )
        )
        if pending_tasks:
            await asyncio.wait(pending_tasks)

    async def _ensure_ready_to_stop(self, entry_name: str) -> None:
        database = self._database
        _logger.debug('Launcher %s is stopping dependents.', entry_name)
        for dependent in database.binds_to.inverses.get(
            entry_name, set()
        ):
            self.stop(dependent)
        _logger.debug(
            'Launcher %s is waiting on dependents.', entry_name
        )
        before = (
            database.before.get(entry_name, set())
            | database.after.inverses.get(entry_name, set())
        )
        pending_tasks = set(
            filter(None, map(self._stop_tasks.get, before))
        )
        if pending_tasks:
            await asyncio.wait(pending_tasks)

    async def _start_main_task(
        self, entry_name: str
    ) -> asyncio.Future[typing.Any]:
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
            return main_task
        except:
            await phile.asyncio.cancel_and_wait(main_task)
            raise

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


class Registry:

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        registry = self

        class DatabaseStopsOnRemove(Database):

            async def remove(self, entry_name: str) -> None:
                await registry.state_machine.stop(entry_name)
                await super().remove(entry_name=entry_name)

        database = DatabaseStopsOnRemove()
        self._state_machine = StateMachine(database=database)

    @property
    def database(self) -> Database:
        return self._state_machine.database

    @property
    def state_machine(self) -> StateMachine:
        return self._state_machine


@contextlib.asynccontextmanager
async def provide_registry(
    capability_registry: phile.capability.Registry,
) -> collections.abc.AsyncIterator[Registry]:
    with capability_registry.provide(launcher_registry := Registry()):
        launcher_name = 'phile_shutdown.target'
        await launcher_registry.database.add(
            launcher_name,
            phile.launcher.Descriptor(
                exec_start=[asyncio.get_running_loop().create_future],
            )
        )
        yield launcher_registry
        _logger.debug('Launcher clean-up starting.')
        await launcher_registry.state_machine.start(launcher_name)
        _logger.debug('Launcher clean-up done.')
