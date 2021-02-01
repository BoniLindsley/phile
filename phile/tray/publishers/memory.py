#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import datetime
import sys
import typing

# External dependencies.
import psutil  # type: ignore[import]

# Internal packages.
import phile
import phile.tray
from . import update


class MemoryFile(phile.tray.File):

    def update(self, memory: psutil.virtual_memory) -> None:
        self.text_icon = f' M{memory.available//1000**3:.0f}'


class TrayFilesUpdater(update.SelfTarget):

    def __init__(
        self,
        *args: typing.Any,
        capabilities: phile.Capabilities,
        prefix: str = '70-phile-tray-memory-',
        refresh_interval: datetime.timedelta = datetime.timedelta(
            seconds=5
        ),
        **kwargs: typing.Any
    ):
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        configuration = capabilities[phile.Configuration]
        self.refresh_interval = refresh_interval
        self.file = MemoryFile(
            path=configuration.tray_directory /
            (prefix + 'available' + configuration.tray_suffix),
        )

    def on_exit(self) -> None:
        self.file.path.unlink(missing_ok=True)

    def __call__(self) -> datetime.timedelta:
        memory = psutil.virtual_memory()
        file = self.file
        file.update(memory=memory)
        file.save()
        return self.refresh_interval


async def run(
    capabilities: phile.Capabilities
) -> int:  # pragma: no cover
    target = TrayFilesUpdater(capabilities=capabilities)
    await update.sleep_loop(target)
    return 0


async def async_main(argv: typing.List[str]) -> int:  # pragma: no cover
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    return await run(capabilities=capabilities)


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
