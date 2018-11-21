# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Andrew Resch <andrewresch@gmail.com>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

import functools

from asynctest import ClockedTestCase

from deluge.loopingcall import LoopingCall, AlreadyRunning, NotRunning


class LoopingCallTests(ClockedTestCase):
    def setUp(self):
        super().setUp()
        self.calls = []
        self.looping_call = LoopingCall(self.func)

    async def tearDown(self):
        try:
            await self.looping_call.stop()
        except NotRunning:
            pass

    async def func(self, value=True):
        # Function to be called in the LoopingCall
        self.calls.append(value)

    async def start_looping_call(self, interval=2, now=True):
        self.looping_call.start(interval, now)
        # The advance(0) is necessary to get the LoopingCalls task to
        # move from pending to started.
        await self.advance(0)

    async def test_running(self):
        self.assertFalse(self.looping_call.running)
        await self.start_looping_call()
        self.assertTrue(self.looping_call.running)
        await self.looping_call.stop()

    async def test_start(self):
        await self.start_looping_call()
        self.assertEqual(len(self.calls), 1)

    async def test_start_already_running(self):
        await self.start_looping_call()
        self.assertRaises(AlreadyRunning, self.looping_call.start, 2)

    async def test_stop(self):
        await self.start_looping_call()
        await self.looping_call.stop()
        await self.advance(4)
        self.assertEquals(len(self.calls), 1)

    async def test_stop_not_running(self):
        await self.assertAsyncRaises(NotRunning, self.looping_call.stop())

    async def test_loop(self):
        await self.start_looping_call()
        await self.advance(2)
        self.assertEqual(len(self.calls), 2)
        await self.advance(2)
        self.assertEqual(len(self.calls), 3)

    async def test_start_not_now(self):
        await self.start_looping_call(now=False)
        self.assertEqual(len(self.calls), 0)

    async def test_start_not_now_after_interval(self):
        await self.start_looping_call(now=False)
        await self.advance(2)
        self.assertEqual(len(self.calls), 1)

    async def test_func_arguments(self):
        async def func(value):
            self.calls.append(value)

        looping_call = LoopingCall(functools.partial(func, value='foobar'))
        looping_call.start(2)
        await self.advance(0)
        self.assertEqual(self.calls, ['foobar'])

    async def test_restart(self):
        await self.start_looping_call()
        self.assertEqual(len(self.calls), 1)
        await self.looping_call.stop()
        await self.start_looping_call()
        self.assertEqual(len(self.calls), 2)
