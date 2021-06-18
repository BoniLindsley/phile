#!/usr/bin/env python3
"""
--------------------------------------
Display tray files in tmux status line
--------------------------------------
"""

# Internal packages.
import phile.tmux
import phile.tmux.control_mode
import phile.tray


async def run(
    control_mode: phile.tmux.control_mode.Client,
    text_icons: phile.tray.TextIcons,
) -> None:
    """Start updating ``status-right`` with tray file changes."""
    control_mode.send_soon(
        phile.tmux.CommandBuilder.set_global_status_right(
            text_icons.current_value
        )
    )
    try:
        # Branch: from `for` to `finally` exit.
        # Covered in `test_stops_gracefully_if_text_icons_stops`.
        # But not detected somehow.
        async for new_text in (  # pragma: no branch
            text_icons.event_queue
        ):
            control_mode.send_soon(
                phile.tmux.CommandBuilder.set_global_status_right(
                    new_text,
                )
            )
    finally:
        control_mode.send_soon(
            phile.tmux.CommandBuilder.unset_global_status_right()
        )
