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
        assert False, 'Unreachable'  # pragma: no cover
