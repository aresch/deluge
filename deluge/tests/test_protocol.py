# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Andrew Resch <andrew.resch@gmail.com>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

import unittest
import zlib

import rencode

from deluge.protocol import DelugeRPCProtocol, MESSAGE_HEADER_SIZE


class FakeTransport:
    def __init__(self):
        self.data = b''

    def write(self, data):
        self.data += data


class Protocol(DelugeRPCProtocol):
    def __init__(self):
        super().__init__()
        self.messages = []

    def message_received(self, message):
        self.messages.append(message)


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.protocol = Protocol()
        self.transport = FakeTransport()
        self.protocol.connection_made(self.transport)

        self.obj1 = {'foo': ('bar', 'baz')}

    def test_send(self):
        self.protocol.send(self.obj1)
        self.assertEquals(
            self.transport.data[MESSAGE_HEADER_SIZE:],
            zlib.compress(rencode.dumps(self.obj1)),
        )

    def test_data_received_one_message(self):
        self.protocol.send(self.obj1)
        self.protocol.data_received(self.transport.data)
        self.assertEquals(self.protocol.messages[0], self.obj1)
        self.assertEquals(len(self.protocol.buf), 0)

    def test_data_received_one_message_in_parts(self):
        self.protocol.send(self.obj1)
        # Send half of the data for the message
        self.protocol.data_received(
            self.transport.data[: round(len(self.transport.data) / 2)]
        )
        self.assertFalse(self.protocol.messages)
        # Send the remaining data of the message
        self.protocol.data_received(
            self.transport.data[round(len(self.transport.data) / 2) :]
        )
        self.assertEquals(self.protocol.messages[0], self.obj1)

    def test_data_received_multiple_one_byte_at_a_time(self):
        self.protocol.send(self.obj1)
        for b in self.transport.data * 10:
            self.protocol.data_received(bytes([b]))
        self.assertEquals(self.protocol.messages[5], self.obj1)
        self.assertEquals(len(self.protocol.messages), 10)
