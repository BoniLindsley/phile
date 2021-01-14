#!/usr/bin/env python3

# Standard library.
import pathlib

# External dependencies.
import PySide2.QtGui


def q_icon_from_specified_theme(
    name: str, theme_name: str
) -> PySide2.QtGui.QIcon:
    """
    Create an icon based on the given `name` only in the given theme.

    See: :func:`q_icon_from_theme`.
    """

    # Getting branch coverage wranings here.
    # Since this is mostly an implementation placeholder for now,
    # there is no point in being strict in testing it.
    # This is true for the `q_icon_from_theme` function too.
    # The coverage can be increased as necessary
    # when the need to implement this properly is needed.

    QIcon = PySide2.QtGui.QIcon
    for theme_search_path in QIcon.themeSearchPaths(
    ):  # pragma: no cover
        theme_directory = pathlib.Path(theme_search_path) / theme_name
        icon_search_pattern = name + '.png'
        possible_icons = sorted(
            theme_directory.rglob(icon_search_pattern)
        )
        for icon_path in possible_icons:
            current_icon = QIcon(str(icon_path))
            if not current_icon.isNull():
                current_icon.name = lambda: name  # type: ignore
                return current_icon
    return QIcon()


def q_icon_from_theme(name: str) -> PySide2.QtGui.QIcon:
    """
    Create an icon based on the given name in the current theme.

    The `offscreen` Qt platform does not seem to implement icon themes.
    This function makes a minimal attempt to find an icon
    based on the specification found in
    https://specifications.freedesktop.org/icon-theme-spec
    but most of it is not implemented.
    This does not try to find a best match,
    nor parse the `index.theme`.
    nor does it fallback to parent themes.
    """
    QIcon = PySide2.QtGui.QIcon
    theme_names_to_try = [
        QIcon.themeName(),
        'hicolor',
        QIcon.fallbackThemeName(),
    ]
    theme_names_to_try = [
        theme_name for theme_name in theme_names_to_try if theme_name
    ]
    for theme_name in theme_names_to_try:
        current_icon = q_icon_from_specified_theme(name, theme_name)
        if not current_icon.isNull():
            return current_icon
    return QIcon()
