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
import phile.configuration
import phile.tray
from . import update

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


class TrayFilesUpdater(update.SelfTarget):

    def __init__(
        self,
        *args,
        configuration: phile.configuration.Configuration,
        prefix: str = '70-phile-tray-battery-',
        refresh_interval: datetime.timedelta = datetime.timedelta(
            seconds=5
        ),
        **kwargs
    ):
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.refresh_interval = refresh_interval
        self.files: typing.Tuple[File, ...] = (
            PercentageFile.from_path_stem(
                configuration=configuration,
                path_stem=prefix + '1-percentage'
            ),
            TimeFile.from_path_stem(
                configuration=configuration, path_stem=prefix + '2-time'
            ),
        )

    def on_exit(self) -> None:
        for file in self.files:
            file.path.unlink(missing_ok=True)

    def __call__(self) -> datetime.timedelta:
        battery_state = psutil.sensors_battery()
        for file in self.files:
            file.update(battery_state)
        for file in self.files:
            file.save()
        return self.refresh_interval


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    configuration = phile.configuration.Configuration()
    with contextlib.suppress(KeyboardInterrupt):
        target = TrayFilesUpdater(configuration=configuration)
        asyncio.run(update.sleep_loop(target))
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
