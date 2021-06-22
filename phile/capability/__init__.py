#!/usr/bin/env python3
"""
.. automodule:: phile.capability.asyncio
"""

# Standard libraries.
import contextlib
import typing

_T_co = typing.TypeVar('_T_co')


class AlreadyEnabled(RuntimeError):
    pass


# TODO[mypy issue #4717]: Remove `ignore[misc]` from uses of this class.
# The `type` type hint does not accept abstract types.
# So an ignore is necessary on all uses with abstract types.
class Registry(dict[type, typing.Any]):

    def __getitem__(self, capability: type[_T_co]) -> _T_co:
        return typing.cast(_T_co, super().__getitem__(capability))

    # Needed for type hinting.
    def __setitem__(  # pylint: disable=useless-super-delegation
        self,
        key: type[_T_co],
        value: _T_co,
    ) -> None:
        super().__setitem__(key, value)

    def set(self, value: _T_co) -> None:
        self.__setitem__(type(value), value)

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
