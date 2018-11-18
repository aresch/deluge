# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Andrew Resch <andrewresch@gmail.com>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

import asyncio
from typing import Callable, Union


class AlreadyRunning(Exception):
    pass


class NotRunning(Exception):
    pass


class LoopingCall:
    task: Union[asyncio.Task, None] = None

    def __init__(self, func: Callable):
        self.func = func

    @property
    def running(self) -> bool:
        return self.task is not None

    def start(self, interval: int, now: bool = True):
        if self.running:
            raise AlreadyRunning()
        self.task = asyncio.create_task(self._run(interval, now))

    async def stop(self):
        if not self.running:
            raise NotRunning()

        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        finally:
            self.task = None

    async def _run(self, interval: int, now:bool = True):
        if now:
            await self.func()
        while True:
            await asyncio.sleep(interval)
            await self.func()
