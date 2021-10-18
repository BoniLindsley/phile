#!/usr/bin/env python3

# Standard library.
import bisect
import dataclasses
import enum
import logging
import typing
import warnings

# Internal packages.
import phile.asyncio.pubsub

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)


class Bisectable(typing.Protocol):
    def __eq__(self, other: object) -> bool:
        ...  # pragma: no cover

    def __lt__(self, other: typing.Any) -> bool:
        ...  # pragma: no cover


_ValueT = typing.TypeVar("_ValueT")
_KeyT = typing.TypeVar("_KeyT", bound=Bisectable)


class EventType(enum.Enum):
    DISCARD = enum.auto()
    INSERT = enum.auto()
    SET = enum.auto()


@dataclasses.dataclass
class Event(typing.Generic[_KeyT, _ValueT]):
    type: EventType
    index: int
    key: _KeyT
    value: _ValueT
    current_keys: list[_KeyT]
    current_values: list[_ValueT]


class Registry(typing.Generic[_KeyT, _ValueT]):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.current_keys: list[_KeyT] = []
        """Read-only for user."""
        self.current_values: list[_ValueT] = []
        """Read-only for user."""
        self.event_queue = phile.asyncio.pubsub.Queue[
            Event[_KeyT, _ValueT]
        ]()

    def close(self) -> None:
        self.event_queue.close()

    def discard(self, key: _KeyT) -> None:
        index = bisect.bisect_left(self.current_keys, key)
        try:
            if self.current_keys[index] != key:
                return
        except IndexError:
            return
        _logger.debug("Removing notification %s", key)
        old_value = self.current_values.pop(index)
        self.current_keys.pop(index)
        self._put_event(
            type=EventType.DISCARD,
            index=index,
            key=key,
            value=old_value,
        )

    def set(self, key: _KeyT, value: _ValueT) -> None:
        index = bisect.bisect_left(self.current_keys, key)
        try:
            old_key = self.current_keys[index]
        except IndexError:
            self._insert(index, key, value)
            return
        if old_key != key:
            self._insert(index, key, value)
            return
        if self.current_values[index] == value:
            return
        _logger.debug("Updating notification %s", key)
        self.current_values[index] = value
        self._put_event(
            type=EventType.SET,
            index=index,
            key=key,
            value=value,
        )

    def _insert(self, index: int, key: _KeyT, value: _ValueT) -> None:
        _logger.debug("Inserting notification %s", key)
        self.current_values.insert(index, value)
        self.current_keys.insert(index, key)
        self._put_event(
            type=EventType.INSERT,
            index=index,
            key=key,
            value=value,
        )

    def _put_event(
        self,
        type: EventType,  # pylint: disable=redefined-builtin
        index: int,
        key: _KeyT,
        value: _ValueT,
    ) -> None:
        try:
            self.event_queue.put(
                Event[_KeyT, _ValueT](
                    type=type,
                    index=index,
                    key=key,
                    value=value,
                    current_keys=self.current_keys.copy(),
                    current_values=self.current_values.copy(),
                )
            )
        except phile.asyncio.pubsub.Node.AlreadySet:
            warnings.warn(
                "Registry should not be changed after closing."
            )
