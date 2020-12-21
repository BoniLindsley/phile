#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import datetime
import sys
import types
import typing

# Internal packages.
import phile.configuration
import phile.tray
from . import update


class TrayFilesUpdater(update.SelfTarget):

    def __init__(
        self,
        *args,
        configuration: phile.configuration.Configuration,
        prefix: str = '90-phile-tray-datetime-',
        **kwargs
    ):
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        File = phile.tray.File
        self.files = tuple(
            File.from_path_stem(
                configuration=configuration, path_stem=prefix + suffix
            ) for suffix in (
                '1-year', '2-month', '3-day', '4-weekday', '5-hour',
                '6-minute'
            )
        )

    def on_exit(self) -> None:
        for file in self.files:
            file.path.unlink(missing_ok=True)

    def __call__(self) -> datetime.timedelta:
        now = datetime.datetime.now()
        datetime_values = (
            now.strftime(' %Y'), now.strftime('-%m'),
            now.strftime('-%d'), now.strftime('w%w'),
            now.strftime(' %H'), now.strftime(':%M')
        )
        for value, file in zip(datetime_values, self.files):
            file.text_icon = value
        for file in self.files:
            file.save()
        return datetime.timedelta(
            seconds=60 - now.second + 1 - now.microsecond / 1_000_000
        )


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    configuration = phile.configuration.Configuration()
    with contextlib.suppress(KeyboardInterrupt):
        target = TrayFilesUpdater(configuration=configuration)
        asyncio.run(update.sleep_loop(target))
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
