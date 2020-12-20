#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import dataclasses
import datetime
import psutil  # type: ignore[import]
import sys
import typing

# Internal packages.
import phile.configuration
import phile.tray

BatteryStatus = typing.Optional[psutil._common.sbattery]


class File(phile.tray.File):

    def update(self, battery_state: BatteryStatus) -> None:
        raise NotImplementedError()


class PercentageFile(File):

    def update(self, battery_state: BatteryStatus) -> None:
        if battery_state is not None:
            percentage_text = f'{battery_state.percent:02.0f}'
        else:
            percentage_text = '-?'
        self.text_icon = f' B:{percentage_text}%'


class TimeFile(File):

    def update(self, battery_state: BatteryStatus) -> None:
        if battery_state is not None and battery_state.secsleft >= 0:
            timedelta = datetime.timedelta
            time_remaining = timedelta(seconds=battery_state.secsleft)
            hour, trailing = divmod(time_remaining, timedelta(hours=1))
            minute = trailing // timedelta(minutes=1)
            remaining_text = f'={hour}h{minute:02}'
        else:
            remaining_text = ''
        self.text_icon = f'{remaining_text}'


@dataclasses.dataclass
class UpdateLoop:

    configuration: dataclasses.InitVar[phile.configuration.Configuration]
    prefix: dataclasses.InitVar[str] = '70-phile-tray-battery-'
    refresh_interval: datetime.timedelta = datetime.timedelta(seconds=5)

    def __post_init__(
        self, configuration: phile.configuration.Configuration,
        prefix: str
    ) -> None:
        self.files: typing.Tuple[File, ...] = (
            PercentageFile.from_path_stem(
                configuration=configuration,
                path_stem=prefix + '1-percentage'
            ),
            TimeFile.from_path_stem(
                configuration=configuration, path_stem=prefix + '2-time'
            ),
        )

    def close(self) -> None:
        for file in self.files:
            file.path.unlink(missing_ok=True)

    async def run(self):
        with contextlib.closing(self):
            while True:
                timeout = self.update().total_seconds()
                await asyncio.sleep(timeout)

    def update(self) -> typing.Optional[datetime.timedelta]:
        battery_state = psutil.sensors_battery()
        for file in self.files:
            file.update(battery_state)
        for file in self.files:
            file.save()
        return self.refresh_interval


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    configuration = phile.configuration.Configuration()
    with contextlib.suppress(KeyboardInterrupt):
        run = UpdateLoop(configuration=configuration).run()
        asyncio.run(run)
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
