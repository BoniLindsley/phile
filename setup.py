#!/usr/bin/env python3

from setuptools import setup  # type: ignore

setup(
    name='phile',
    version='0.0.0.1',
    description='A file-based notification management',
    author='Boni Lindsley',
    author_email='boni.lindsley@gmail.com',
    packages=[
        'phile',
        'phile.data',
        'phile.notify',
        'phile.PySide2',
        'phile.tmux',
        'phile.tray',
        'phile.trigger',
        'phile.watchdog',
    ],
    license='MIT',
    install_requires=[
        'pathvalidate',
        'portalocker',
        'PySide2',
        'watchdog',
    ],
    entry_points={
        'console_scripts': [
            'phile = phile.__main__:main',
            'phile-notify = phile.notify.__main__:main',
            'phile-tray-tmux = phile.tray.tmux:main',
        ],
        'gui_scripts': [
            'phile-notify-gui = phile.notify.gui:main',
            'phile-tray-gui = phile.tray.gui:main',
        ],
    },
    extras_require={
        'dev': [
            'coverage',
            'mypy',
            'psutil',
            'recommonmark',
            'sphinx',
            'tox',
            'yapf',
        ],
    },
    # Requires Python 3.6 because Python is dropping support
    # for version 3.5 after September 2020 (as for 2020-09-05).
    # Reference: https://www.python.org/dev/peps/pep-0478/
    python_requires='>= 3.6',
    package_data={
        'phile.tray': [
            'resources/icons/blank/64x64/status/phile-tray-empty.png',
            'resources/icons/blank/64x64/status/phile-tray-new.png',
            'resources/icons/blank/64x64/status/phile-tray-read.png',
            'resources/icons/blank/index.theme',
        ],
    },
)
