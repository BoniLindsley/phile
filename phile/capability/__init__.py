#!/usr/bin/env python3
"""
.. automodule:: phile.capability.asyncio
.. automodule:: phile.capability.pyside2
.. automodule:: phile.capability.tmux
"""

# Standard libraries.
import collections.abc
import contextlib
import functools
import types
import typing

# Internal modules.
import phile

NullaryCallable = typing.Callable[[], typing.Any]

_T_co = typing.TypeVar('_T_co')


class AlreadyEnabled(RuntimeError):
    pass


class Registry(phile.Capabilities):

    def provide(
        self,
        value: _T_co,
        capability: typing.Optional[type[_T_co]] = None,
    ) -> contextlib.AbstractContextManager[typing.Any]:
        if capability is None:
            capability = type(value)
        value_set = self.setdefault(capability, value)
        if value_set != value:
            raise AlreadyEnabled()
        with contextlib.ExitStack() as stack:
            stack.callback(self.pop, capability, None)
            return stack.pop_all()
        assert False, 'Unreachable'


class Providers:

    def __init__(
        self,
        *args: typing.Any,
        target_registry: Registry,
        undo_stack: contextlib.ExitStack,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.target_registry = target_registry
        self.undo_stack = undo_stack

    def register(
        self,
        value: _T_co,
        capability: typing.Optional[type[_T_co]] = None,
    ) -> None:
        self.undo_stack.enter_context(
            self.target_registry.provide(value, capability)
        )


class CleanUps:

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.callbacks = set[NullaryCallable]()

    @contextlib.contextmanager
    def connect(
        self, callback: NullaryCallable
    ) -> collections.abc.Iterator[None]:
        try:
            self.callbacks.add(callback)
            yield
        finally:
            self.callbacks.discard(callback)

    @contextlib.contextmanager
    def provide_trigger(
        self, capability_registry: Registry
    ) -> collections.abc.Iterator[None]:
        # Need to scope import to not always import PySide2.
        # pylint: disable=import-outside-toplevel
        import phile.trigger  # pylint: disable=redefined-outer-name
        with phile.trigger.Provider(
            callback_map={'quit': self.run},
            registry=capability_registry[phile.trigger.Registry],
        ) as provider:
            provider.show_all()
            yield

    def run(self) -> None:
        for callback in self.callbacks.copy():
            callback()
