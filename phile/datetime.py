#!/usr/bin/env python3

# Standard libraries.
import datetime
import typing


def timedelta_to_seconds(
    timedelta: typing.Optional[datetime.timedelta] = None
) -> typing.Optional[float]:
    """Convert timedelta to seconds, preserving :data:`None`."""
    if timedelta is None:
        return None
    else:
        return timedelta.total_seconds()
