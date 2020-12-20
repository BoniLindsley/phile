#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import dataclasses
import datetime
import sys
import typing

# Internal packages.
import phile.configuration
import phile.tray


@dataclasses.dataclass
class UpdateLoop:

    configuration: dataclasses.InitVar[phile.configuration.Configuration]
    prefix: dataclasses.InitVar[str] = '90-phile-tray-datetime-'

    def __post_init__(
        self, configuration: phile.configuration.Configuration,
        prefix: str
    ) -> None:
        File = phile.tray.File
        self.files = tuple(
            File.from_path_stem(
                configuration=configuration, path_stem=prefix + suffix
            ) for suffix in (
                '1-year', '2-month', '3-day', '4-weekday', '5-hour',
                '6-minute'
            )
        )

    def close(self) -> None:
        for file in self.files:
            file.path.unlink(missing_ok=True)

    async def run(self) -> None:
        with contextlib.closing(self):
            while True:
                timeout = self.update().total_seconds()
                await asyncio.sleep(timeout)

    def update(self) -> datetime.timedelta:
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
        run = UpdateLoop(configuration=configuration).run()
        asyncio.run(run)
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
