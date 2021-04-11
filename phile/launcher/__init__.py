#!/usr/bin/env python3
"""
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
import types
import typing

# Internal modules.
import phile

#Command = collections.abc.Coroutine[typing.Any, typing.Any, typing.Any]
Awaitable = collections.abc.Awaitable[typing.Any]
Command = collections.abc.Callable[[], Awaitable]
CommandLines = list[Command]
NullaryCallable = collections.abc.Callable[[], typing.Any]


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

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
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
        self.binds_to: dict[str, set[str]] = {}
        """Dependencies of launchers."""
        self.bound_by: dict[str, set[str]] = {}
        """Dependents of launchers."""
        self.exec_start: dict[str, CommandLines] = {}
        """Coroutines to call to start a launcher."""
        self.exec_stop: dict[str, CommandLines] = {}
        """Coroutines to call to stop a launcher."""
        self.remover: dict[str, NullaryCallable] = {}
        """Callback to call to remove launchers from the database."""
        self.type: dict[str, Type] = {}
        """Initialisation and termination conditions of launchers."""

    def add(self, entry_name: str, descriptor: Descriptor) -> None:
        """Not thread-safe."""
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                self._update_descriptor(entry_name, descriptor)
            )
            stack.enter_context(self._update_type(entry_name))
            stack.enter_context(self._update_exec_start(entry_name))
            stack.enter_context(self._update_exec_stop(entry_name))
            stack.enter_context(self._update_binds_to(entry_name))
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

    def remove(self, entry_name: str) -> None:
        entry_remover = self.remover.pop(entry_name, None)
        if entry_remover is not None:
            entry_remover()

    def contains(self, entry_name: str) -> bool:
        return entry_name in self.remover
