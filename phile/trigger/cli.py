#!/usr/bin/env python3
"""
-------------------------------------
Trigger manipulation using :mod:`cmd`
-------------------------------------
"""

# Standard library.
import asyncio
import collections.abc
import cmd
import contextlib
import pathlib
import queue
import shlex
import sys
import typing

# External dependencies.
import watchdog.observers

# Internal packages.
import phile
import phile.notify
import phile.watchdog

_Self = typing.TypeVar('_Self')
_T = typing.TypeVar('_T')


class IterableSimpleQueue(queue.SimpleQueue[_T]):

    def __iter__(self: _Self) -> _Self:
        return self

    def __next__(self) -> _T:
        try:
            return self.get_nowait()
        except queue.Empty:
            raise StopIteration


class Cache:

    def __init__(
        self, *args: typing.Any, trigger_root: pathlib.Path,
        trigger_suffix: str, **kwargs: typing.Any
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.trigger_root = trigger_root
        self.trigger_suffix = trigger_suffix
        self.available_triggers = set[pathlib.Path]()
        self.expired_triggers = IterableSimpleQueue[pathlib.Path]()
        self.known_triggers = dict[int, pathlib.Path]()
        self.trigger_ids = dict[pathlib.Path, int]()
        self.next_new_id = 1

    def refresh(self) -> None:
        self.purge()
        put = self.expired_triggers.put
        for trigger in sorted(
            self.trigger_root.rglob('*' + self.trigger_suffix)
        ):
            put(trigger)
        self.update_expired()

    def execute(
        self, trigger_ids: collections.abc.Iterable[int]
    ) -> None:
        triggers = [
            self.known_triggers[trigger_id] for trigger_id in trigger_ids
        ]
        for trigger in triggers:
            trigger.unlink(missing_ok=True)

    def update_expired(self) -> None:
        expired_triggers = list(self.expired_triggers)
        self.assign_ids(expired_triggers)
        self.update_availability(expired_triggers)

    def update_availability(
        self, triggers: collections.abc.Iterable[pathlib.Path]
    ) -> None:
        available_triggers = self.available_triggers
        available_triggers.difference_update(triggers)
        available_triggers.update(
            trigger for trigger in triggers if trigger.is_file()
        )

    def assign_ids(
        self, triggers: collections.abc.Iterable[pathlib.Path]
    ) -> None:
        trigger_ids = self.trigger_ids
        known_triggers = self.known_triggers
        for trigger in triggers:
            new_id = self.next_new_id
            trigger_id = trigger_ids.setdefault(trigger, new_id)
            if trigger_id == new_id:
                self.next_new_id += 1
                known_triggers[new_id] = trigger

    def purge(self) -> None:
        self.available_triggers.clear()
        self.known_triggers.clear()
        self.trigger_ids.clear()
        self.next_new_id = 1

    def to_name(self, path: pathlib.Path) -> str:
        assert self.is_trigger(path)
        return str(path.relative_to(self.trigger_root))

    def is_trigger(self, path: pathlib.Path) -> bool:
        return path.is_relative_to(
            self.trigger_root
        ) and path.suffix == self.trigger_suffix


class Prompt(cmd.Cmd):

    def __init__(
        self, *args: typing.Any, cache: Cache, **kwargs: typing.Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.cache = cache

    def do_EOF(self, arg: str) -> typing.Literal[True]:
        return True

    def do_refresh(self, arg: str) -> None:
        self.cache.refresh()

    def do_exe(self, arg: str) -> None:
        self.do_execute(arg)

    def do_execute(self, arg: str) -> None:
        argv = shlex.split(arg)
        try:
            trigger_ids = [int(entry) for entry in argv]
        except ValueError as error:
            self.stdout.write(
                'Unable to parse trigger id. {error}'.format(
                    error=error
                )
            )
            return
        self.cache.execute(trigger_ids)

    def do_list(self, arg: str) -> None:
        cache = self.cache
        to_name = cache.to_name
        write = self.stdout.write
        for trigger_id, path in cache.known_triggers.items():
            if path in cache.available_triggers:
                write(
                    '{trigger_id} {name}\n'.format(
                        trigger_id=trigger_id, name=to_name(path)
                    )
                )

    def do_list_all(self, arg: str) -> None:
        cache = self.cache
        to_name = cache.to_name
        write = self.stdout.write
        for trigger_id, path in cache.known_triggers.items():
            write(
                '{trigger_id} {name}\n'.format(
                    trigger_id=trigger_id, name=to_name(path)
                )
            )

    def onecmd(self, line: str) -> bool:
        if line != 'EOF':
            self.cache.update_expired()
        return super().onecmd(line)


async def run(
    capabilities: phile.Capabilities
) -> int:  # pragma: no cover
    configuration = capabilities[phile.Configuration]
    observer = capabilities[watchdog.observers.api.BaseObserver]
    trigger_root = configuration.trigger_root
    trigger_suffix = configuration.trigger_suffix
    cache = Cache(
        trigger_root=trigger_root, trigger_suffix=trigger_suffix
    )
    prompt = Prompt(cache=cache)
    with phile.watchdog.Scheduler(
        path_filter=cache.is_trigger,
        path_handler=cache.expired_triggers.put,
        watch_recursive=True,
        watched_path=trigger_root,
        watching_observer=observer,
    ):
        cache.refresh()
        await asyncio.to_thread(prompt.cmdloop)
    return 0


async def async_main(argv: list[str]) -> int:  # pragma: no cover
    del argv
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    async with phile.watchdog.observers.async_open() as observer:
        capabilities[watchdog.observers.api.BaseObserver] = observer
        await run(capabilities=capabilities)
    return 0


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    if argv is None:
        argv = sys.argv
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
