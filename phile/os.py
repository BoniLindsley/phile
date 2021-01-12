#!/usr/bin/env python3

# Standard libraries.
import os
import typing


class Environ:
    """For using environment variables and restoring later."""

    def __init__(self, *args, **kwargs) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._source_dict = os.environ
        self._backup_dict: typing.Dict[str, typing.Optional[str]] = {}

    def restore(self) -> None:
        source_dict = self._source_dict
        for key, value in self._backup_dict.items():
            if value is None:
                source_dict.pop(key, None)
            else:
                source_dict[key] = value

    def set(self, **kwargs) -> None:
        backup_dict = self._backup_dict
        source_dict = self._source_dict
        for key, value in kwargs.items():
            backup_dict[key] = source_dict.get(key)
            if value is None:
                source_dict.pop(key, None)
            else:
                source_dict[key] = value
