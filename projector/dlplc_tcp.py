# -*- coding: utf8 -*-
"""
    This file is part of DLPLC Interface.

    DLPLC Interface is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    DLPLC Interface is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with DLPLC Interface.  If not, see <http://www.gnu.org/licenses/>.
"""
"""
This module implements some commands as specified
in Texas Instrument Document
    * DLPU007C (January 2012 – Revised September 2012)
This includes connecting and sending commands to and
parsing responses from a DLP LightCrafter (dlplc) module.

The dlplc module is denoted as "device", the PC as "host".

by Jonas Hagen <jonas.hagen@students.unibe.ch>
"""

import socket
import struct
import time

class LightCrafterTCP:
    """
    Represents a DLP LightCrafter and its connection.
    """

    tcp_ip = '192.168.1.100'
    tcp_port = 0x5555
    buffer_size = 1024
    retries = 3

    def connect(self, ip="", port=0):
        """
        Try to connect to the dlplc.
        
        If no ip and port is specified, standard settings are used:
            192.168.1.100:0x5555
        Retruns True if connection is established, False otherwise.
        """

        if ip != "":
            self.tcp_ip = ip
        if port != 0:
            self.tcp_port = port

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
            self.socket = None
        else:
            try:
                self.socket.connect((self.tcp_ip, self.tcp_port))
            except socket.error as msg:
                self.socket.close()
                self.socket = None
        if self.socket is None:
            print("Error: could not open socket to %s:%d".format(self.tcp_ip, self.tcp_port))
            return False

        return True

    def close(self):
        try:
            self.socket.close()
            self.socket=None
            print("Connection closed.")
        except:
            print("Nothing to close.")
    
    def send(self, packet):
        """
        Send a previously packed packet.
        
        If the system is busy, a defined number of retries will be made.
        Raises BusyError if all retries fail.
        Returns the response as an unpacked Packet.
        """
        tries = 0
        p = Packet()
        while tries < self.retries:
            self.socket.send(packet.pack())
            # wait for acknowledgement
            response = self.socket.recv(self.buffer_size)
            p.unpack(response)
            if p.p_type == Packet.PT_LC_SYSTEM_BUSY:
                tries += 1
                print("System Busy. Retry.")
                time.sleep(0.5)
            else:
                break

        if tries == self.retries:
            raise BusyError
        return p

    def cmd(self, p_type, cmd1, cmd2, data):
        """
        Generic method to send a simple command to the dlplc.

        If the data passed is too long, it gets split into
        multiple packets.
        Raises Error if the response contains an error message.
        """
        size = 65535
        if len(data) <= size:
            p = Packet()
            p.set_header(p_type, cmd1, cmd2)
            p.set_payload(data)
            response = self.send(p)
            response.raise_if_error()
        else:
            parts = [data[i:i+size] for i in range(0, len(data), size)]

            for i, part in enumerate(parts):
                if i == 0:
                    flag = Packet.F_BEGIN
                elif i == len(parts)-1:
                    flag = Packet.F_END
                else:
                    flag = Packet.F_INTER

                p = Packet()
                p.set_header(p_type, cmd1, cmd2, flag)
                p.set_payload(part)
                response = self.send(p)
                response.raise_if_error()

        return response

    def cmd_version_string(self, number):
        """See [DLPU007C]."""
        return self.cmd(Packet.PT_H_READ, 0x01, 0x00, "%c"%number)

    def cmd_current_display_mode(self, number):
        """See [DLPU007C]."""
        return self.cmd(Packet.PT_H_WRITE, 0x01, 0x01, "%c"%number)

    def cmd_current_video_mode(self, frame_rate, bit_depth, led_color):
        """See [DLPU007C]."""
        return self.cmd(Packet.PT_H_WRITE, 0x02, 0x01, "%c%c%c" % (frame_rate, bit_depth, led_color))

    def cmd_current_test_pattern(self, number):
        """See [DLPU007C]."""
        if number >= 0 and number <= 13: 
            return self.cmd(Packet.PT_H_WRITE, 0x01, 0x03, "%c"%number)
        else:
            return None

    def cmd_pattern_sequence_setting(self, settings):
        """Set the pattern display parameters.
        
        Settings is a dict with some of the following keys:
        depth, num, include_inverted, trigger, delay,
        period, exposure, led."""

        val = {
            "depth":1,
            "num":1,
            "include_inverted":1,
            "trigger":1, # Auto trigger (time)
            "delay":0, # microseconds
            "period":200000, # microseconds
            "exposure":200000, # microseconds
            "led":2 # Blue
            }
        val.update(settings)
        data = struct.pack("4B 3I B B",
            val["depth"],
            val["num"],
            val["include_inverted"],
            val["trigger"],
            val["delay"],
            val["period"],
            val["exposure"],
            val["led"],
            0) # workaround, see: http://e2e.ti.com/support/dlp__mems_micro-electro-mechanical_systems/f/850/p/219181/772176.aspx#772176
        print(val)
        return self.cmd(Packet.PT_H_WRITE, 0x04, 0x00, data)

    def cmd_pattern_definition(self, patterns):
        """
        Set the patterns to be displayed.
        
        patterns is a list of Windows BMP data strings.
        """
        for i,pattern in enumerate(patterns):
            data = struct.pack("B %ds"%len(pattern), i, pattern)
            response = self.cmd(Packet.PT_H_WRITE, 0x04, 0x01, data)

        return True

    def cmd_start_pattern_sequence(self, play):
        """See [DLPU007C]."""
        start = 1 if play else 0
        return self.cmd(Packet.PT_H_WRITE, 0x04, 0x02, "%c"%start)

    def cmd_static_image(self, image):
        """
        Load a static image.

        image is a stirng of Windows BMP encoded data.
        """
        return self.cmd(Packet.PT_H_WRITE, 0x01, 0x05, image)

    def cmd_advance_pattern_sequence(self):
        return self.cmd(Packet.PT_H_WRITE, 0x04, 0x03, "")

    def cmd_display_pattern(self, number):
        data = struct.pack("H", number)
        return self.cmd(Packet.PT_H_WRITE, 0x04, 0x05, data)

class Error(Exception):
    def __init__(self, packet):
        self.number = ord(packet.data[0])
        self.packet = packet
    def __str__(self):
        s = "\nDevice returned Error %s "%hex(self.number)
        s += "\nCommand was %s %s"%(hex(self.packet.cmd1), hex(self.packet.cmd2))
        s += "\nSee [DLPU007C, section 2.1.2] for details."
        s += "\n-------- Response Packet Data --------\n"
        s += str(self.packet)
        s += "\n--------------------------------------\n"
        return s

class BusyError(Exception):
    def __init__(self):
        pass
    def __str__(self):
        return "Device Busy."

class Packet():
    """
    Pack and parse the TCP Packet as defined in [DLPU007C].
    """
    # Packet Types
    PT_LC_SYSTEM_BUSY = 0
    PT_LC_ERROR = 1
    PT_H_WRITE = 2
    PT_LC_WRITE = 3
    PT_H_READ = 4
    PT_LC_READ = 5
    # Flags
    F_COMPLETE = 0
    F_BEGIN = 1
    F_INTER = 2
    F_END = 3
    # Variables
    ORDER = '<' # '<' means little endian
    p_type = 2
    cmd1 = 0
    cmd2 = 0
    flags = 0
    data = '%c'%(0)
    size = 1
    checksum = 0

    def set_header(self, p_type, cmd1, cmd2, flags=0x00):
        """
        Set the header data: Packet type, cmd1, cmd2 and flags.
        """
        self.p_type = p_type
        self.cmd1 = cmd1
        self.cmd2 = cmd2
        self.flags = flags

    def set_payload(self, data):
        """
        Set the payload data string.
        """
        if len(data) == 0:
            self.size = 1
            self.data = "%c"%0
        else:
            self.size = len(data)
            self.data = data

    def build_checksum(self):
        size_low, size_high = struct.unpack("BB",struct.pack("H", self.size))
        checksum = self.p_type + self.cmd1 + self.cmd2
        checksum += self.flags + size_low + size_high
        for c in self.data:
            checksum += ord(c)
        checksum = checksum % 0x100
        return checksum

    def check_checksum(self, checksum):
        return checksum == self.build_checksum()

    def pack(self):
        """
        Returns the packed binary data.
        """
        self.checksum = self.build_checksum()
        format_string = '{}4BH{}sB'.format(self.ORDER,self.size).encode('ascii')
        p = struct.pack(format_string,
            self.p_type,
            self.cmd1, self.cmd2,
            self.flags,
            self.size,
            self.data.encode('ascii'),
            self.checksum);
        self.packet = p
        return p

    def unpack(self, packet):
        """Unpacks a binary string."""
        format_string = '{}4BH'.format(self.ORDER).encode('ascii')
        (self.p_type,
        self.cmd1, self.cmd2,
        self.flags,
        self.size) = struct.unpack(format_string, packet[:6])
        format_string = '{}{}sB'.format(self.ORDER, self.size).encode('ascii')
        self.data, self.checksum = struct.unpack(
            format_string, packet[6:])

        return self.check_checksum(self.checksum)

    def raise_if_error(self):
        """
        Raise an Error or BusyError if packet reports an error.
        """
        if self.p_type == self.PT_LC_ERROR:
            raise Error(self)
        if self.p_type == self.PT_LC_SYSTEM_BUSY:
            raise BusyError()

    def __repr__(self):
        p_type_dict = (
            'LightCrafter System Busy Packet',
            'LightCrafter Error Packet',
            'Host Write Command Packet',
            'LightCrafter Write Response Packet',
            'Host Read Command Packet',
            'LightCrafter Read Response Packet')
        flags_dict = (
            'Complete data',
            'Beginning of the data',
            'Intermediate data',
            'Last data')
        s = ""
        s+="<"+":".join(c.encode('hex') for c in self.pack())+">"
        s+="\n0 Packet Type:   %s %s"%(hex(self.p_type),p_type_dict[self.p_type])
        s+="\n1 CMD1 & CMD2:   %s %s"%(hex(self.cmd1),hex(self.cmd2))
        s+="\n3 Flags:         %s %s"%(hex(self.flags),flags_dict[self.flags])
        s+="\n4 Payload Length:%d"%self.size
        s+="\n6 Data Payload:  %s"%(" ".join(c.encode('hex') for c in self.data))
        s+="\n  Data String:   %s"%self.data
        s+="\n%d Checksum:      %s"%((6+self.size),hex(self.checksum))
        return s

    def show(self):
        print(self)


def main():
    #dlplc = LightCrafterTCP()
    #dlplc.connect()
    #dlplc.build_packet(0x02, 0x01, 0x00, 0x00)
    p = Packet();
    p.set_header(0x02, 0x01, 0x00)
    #p.set_payload("%c"%0x00)
    p.show()
    p.pack()

if __name__ == "__main__":
    main()
