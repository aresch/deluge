# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Andrew Resch <andrew.resch@gmail.com>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

import asyncio
import logging
import struct
import zlib

import rencode

log = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
MESSAGE_HEADER_FORMAT = '!BI'
MESSAGE_HEADER_SIZE = struct.calcsize(MESSAGE_HEADER_FORMAT)


class InvalidVersion(Exception):
    pass


class DelugeRPCProtocol(asyncio.Protocol):
    """
    Data messages are transfered using very a simple protocol.
    Data messages are transfered with a header containing
    the length of the data to be transfered (payload).

    """

    def __init__(self):
        self.buf = bytearray()
        self.bytes_received = 0
        self.bytes_sent = 0
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def send(self, data):
        """
        Send data.

        :param data: data to be transfered in a data structure serializable by rencode.

        """
        body = zlib.compress(rencode.dumps(data))
        body_len = len(body)
        message = struct.pack(
            '{}{}s'.format(MESSAGE_HEADER_FORMAT, body_len),
            PROTOCOL_VERSION,
            body_len,
            body,
        )
        self.bytes_sent += len(message)
        self.transport.write(message)

    def data_received(self, data):
        """
        This method is called whenever data is received.

        :param data: data received as sent by send()
        """
        self.buf += data
        self.bytes_received += len(data)
        try:
            while len(self.buf) > MESSAGE_HEADER_SIZE:
                with memoryview(self.buf) as m:
                    version, size = self.unpack_header(m)

                    if len(m) - MESSAGE_HEADER_SIZE < size:
                        # The buffer does not contain the full message so break
                        # out of the loop and wait for more data to be received.
                        break

                    with m[MESSAGE_HEADER_SIZE : size + MESSAGE_HEADER_SIZE] as msg:
                        self.message_received(
                            rencode.loads(zlib.decompress(msg), decode_utf8=True)
                        )

                del self.buf[: MESSAGE_HEADER_SIZE + size]
        except InvalidVersion as e:
            log.warning(e)
            self.buf = bytearray()

    @staticmethod
    def unpack_header(data):
        """
        Unpack the header portion of a message.

        :param data:
        """
        version, size = struct.unpack(MESSAGE_HEADER_FORMAT, data[:MESSAGE_HEADER_SIZE])

        if version != PROTOCOL_VERSION:
            raise InvalidVersion(
                'Received invalid protocol version: {}. PROTOCOL_VERSION is {}.'.format(
                    version, PROTOCOL_VERSION
                )
            )

        return version, size

    def get_bytes_recv(self):
        """
        Returns the number of bytes received.

        :returns: the number of bytes received
        :rtype: int

        """
        return self.bytes_received

    def get_bytes_sent(self):
        """
        Returns the number of bytes sent.

        :returns: the number of bytes sent
        :rtype: int

        """
        return self.bytes_sent

    def message_received(self, message):
        """Override this method to receive the complete message"""
        pass
