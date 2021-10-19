#!/usr/bin/env python3

# Standard libraries.
import builtins
import contextlib
import dataclasses
import enum
import typing

# Internal packages.
import phile.asyncio.pubsub

_T = typing.TypeVar("_T")
_T_co = typing.TypeVar("_T_co")


class EventType(enum.Enum):
    DEL = enum.auto()
    SET = enum.auto()


@dataclasses.dataclass
class Event:
    type: EventType
    capability: (
        builtins.type[object]  # pylint: disable=unsubscriptable-object
    )


class AlreadyEnabled(RuntimeError):
    pass


class _PopItemDefaultSentinel:
    pass


_pop_item_default_sentinel = _PopItemDefaultSentinel()


# TODO[mypy issue #4717]: Remove `ignore[misc]` from uses of this class.
# The `type` type hint does not accept abstract types.
# So an ignore is necessary on all uses with abstract types.
class Registry(dict[type, typing.Any]):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.event_queue = phile.asyncio.pubsub.Queue[Event]()

    def __delitem__(self, capability: type[_T_co]) -> None:
        super().__delitem__(capability)
        self.event_queue.put(
            Event(type=EventType.DEL, capability=capability)
        )

    def __getitem__(self, capability: type[_T_co]) -> _T_co:
        return typing.cast(_T_co, super().__getitem__(capability))

    def __setitem__(self, key: type[_T_co], value: _T_co) -> None:
        super().__setitem__(key, value)
        self.event_queue.put(Event(type=EventType.SET, capability=key))

    @typing.overload  # type: ignore[override]
    def pop(
        self,
        capability: type[_T_co],
    ) -> _T_co:
        ...

    @typing.overload
    def pop(
        self,
        capability: type[_T_co],
        default: _T,
    ) -> typing.Union[_T_co, _T]:
        ...

    def pop(
        self,
        capability: type[_T_co],
        default: (
            typing.Union[_T, _PopItemDefaultSentinel]
        ) = _pop_item_default_sentinel,
    ) -> typing.Union[_T_co, _T]:
        try:
            popped_value: _T_co = super().pop(capability)
        except KeyError:
            if default is _pop_item_default_sentinel:
                raise
            assert not isinstance(default, _PopItemDefaultSentinel)
            return default
        self.event_queue.put(
            Event(type=EventType.DEL, capability=capability)
        )
        return popped_value

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
        self.event_queue.put(
            Event(type=EventType.SET, capability=capability)
        )
        with contextlib.ExitStack() as stack:
            stack.callback(self.pop, capability, None)
            return stack.pop_all()
        assert False, "Unreachable"  # pragma: no cover
