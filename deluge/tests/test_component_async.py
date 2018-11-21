# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Andrew Resch <andrewresch@gmail.com>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

import asynctest

import deluge.component_async as component


class ComponentTester(component.Component):
    start_count: int = 0
    stop_count: int = 0
    update_count: int = 0
    pause_count: int = 0
    shutdown_count: int = 0

    async def start(self):
        self.start_count += 1

    async def stop(self):
        self.stop_count += 1

    async def update(self):
        self.update_count += 1

    async def pause(self):
        self.pause_count += 1

    async def shutdown(self):
        self.shutdown_count += 1


class TestComponent(asynctest.ClockedTestCase):
    async def tearDown(self):
        for c in list(component._ComponentRegistry.components.values()):
            await component.deregister(c)

    async def test_register(self):
        c = ComponentTester('test_component')
        self.assertEqual(component.get('test_component'), c)
        with self.assertRaises(component.AlreadyRegistered):
            ComponentTester('test_component')

    async def test_start(self):
        c = ComponentTester('test_component')
        await component.start(['test_component'])
        await self.advance(0)
        self.assertEqual(c.start_count, 1)
        self.assertEqual(c.update_count, 1)

    async def test_stop(self):
        c = ComponentTester('test_component')
        await component.start(['test_component'])
        self.assertEqual(c.start_count, 1)
        await component.stop(['test_component'])
        self.assertEqual(c.stop_count, 1)

    async def test_update(self):
        c = ComponentTester('test_component')
        await component.start(['test_component'])
        await self.advance(0)
        self.assertEqual(c.update_count, 1)
        await self.advance(1)
        self.assertEqual(c.update_count, 2)

    async def test_pause(self):
        c = ComponentTester('test_component')
        await self.assertAsyncRaises(
            component.WrongState, component.pause(['test_component'])
        )
        await component.start(['test_component'])
        await self.advance(0)
        self.assertEqual(c.update_count, 1)
        await component.pause(['test_component'])
        await self.advance(5)
        self.assertEqual(c.update_count, 1)

    async def test_resume(self):
        c = ComponentTester('test_component')
        await self.assertAsyncRaises(
            component.WrongState, component.resume(['test_component'])
        )
        await component.start(['test_component'])
        await self.advance(0)
        await component.pause(['test_component'])
        await self.advance(5)
        self.assertEqual(c.update_count, 1)
        await component.resume(['test_component'])
        await self.advance(0)
        self.assertEqual(c.update_count, 2)

    async def test_shutdown(self):
        c = ComponentTester('test_component')
        await component.shutdown()
        self.assertEqual(c.shutdown_count, 1)
        await self.assertAsyncRaises(
            component.WrongState, component.start(['test_component'])
        )

    async def test_deregister(self):
        c = ComponentTester('test_component')
        await component.deregister(c)
        await self.assertAsyncRaises(component.NotRegistered, component.deregister(c))

    async def test_depend(self):
        c1 = ComponentTester('test_component1')
        c2 = ComponentTester('test_component2', depend=['test_component1'])
        c3 = ComponentTester('test_component3', depend=['test_component2'])

        await component.start(['test_component2'])
        self.assertEquals(c1.start_count, 1)
        self.assertEquals(c2.start_count, 1)
        self.assertEquals(c3.start_count, 0)
        await component.start(['test_component3'])
        self.assertEquals(c1.start_count, 1)
        self.assertEquals(c2.start_count, 1)
        self.assertEquals(c3.start_count, 1)
        await component.stop(['test_component2'])
        self.assertEquals(c1.stop_count, 0)
        self.assertEquals(c2.stop_count, 1)
        self.assertEquals(c3.stop_count, 1)
