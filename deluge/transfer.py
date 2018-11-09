# -*- coding: utf-8 -*-
#
# Copyright (C) 2012 Bro <bro.development@gmail.com>
# Copyright (C) 2018 Andrew Resch <andrewresch@gmail.com>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

from deluge.protocol import DelugeRPCProtocol


class DelugeTransferProtocol(DelugeRPCProtocol):
    """
    Twisted compatibility class.
    """
    def dataReceived(self, data):
        self.data_received(data)

    def transfer_message(self, message):
        self.send(message)
