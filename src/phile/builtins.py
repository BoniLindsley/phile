#!/usr/bin/env python3

# Standard libraries.
import contextlib
import types
import typing

_Key = typing.TypeVar("_Key")
_Value = typing.TypeVar("_Value")


def provide_item(
    target: dict[_Key, _Value],
    key: _Key,
    value: _Value,
) -> contextlib.AbstractContextManager[None]:
    class Popper(contextlib.AbstractContextManager[None]):
        def __exit__(
            self,
            exc_type: typing.Optional[typing.Type[BaseException]],
            exc_value: typing.Optional[BaseException],
            traceback: typing.Optional[types.TracebackType],
        ) -> None:
            del exc_type
            del exc_value
            del traceback
            with contextlib.suppress(KeyError):
                del target[key]

    target[key] = value
    return Popper()
