import collections.abc
import typing


def filter_paths(
    paths: list[str],
    included_patterns: typing.Optional[list[str]] = ...,
    excluded_patterns: typing.Optional[list[str]] = ...,
    case_sensitive: bool = ...
) -> collections.abc.Iterator[str]:
    ...


def match_any_paths(
    paths: list[str],
    included_patterns: typing.Optional[list[str]] = ...,
    excluded_patterns: typing.Optional[list[str]] = ...,
    case_sensitive: bool = ...
) -> bool:
    ...
