"""Reliable Data Transfer over Unreliable Transport Layer Using Go-Back-N Strategy"""

__author__ = 'Jeeken (Wang Ziqin)'
__email__ = '11712310@mail.sustc.edu.cn'


# TODO:
# - Connection Establishment
# - Full duplex support

import logging
import signal
import struct

from collections import deque
from socket import timeout as TimeoutException
from typing import Tuple, Union
from udp import UDPsocket


class socket(UDPsocket):
    """
    Connectionless Reliable Data Transfer Socket
    """
    MAX_RETRY_TIMES = 5
    TIMEOUT = .5
    WIN_SIZE = 6

    def __init__(self):
        super().__init__()

        # set timeout handler
        def alarm_handler(signum, frame):
            # logging.debug('SIGALRM: timed out!')
            raise TimeoutException
        signal.signal(signal.SIGALRM, alarm_handler)

    def recvfrom(self) -> Tuple[bytes, tuple]:
        rcvd_data = bytearray()
        expected = 0
        ack = RDTSegment(None, seq_num=0, ack_num=RDTSegment.SEQ_NUM_BOUND-1, ack=True)
        # self.settimeout(socket.TIMEOUT)
        timeout_count = -1
        logging.info('ready to receive...')
        while True:
            try:
                # segment_raw, remote_address = super().recvfrom(RDTSegment.SEGMENT_LEN)
                segment_raw, remote_address = self._timeout_recvfrom(RDTSegment.SEGMENT_LEN)
                logging.debug('received raw segment')
                timeout_count = 0  # no timeout, reset
                segment = RDTSegment.parse(segment_raw)
                logging.info('expected: #%d, received: #%d', expected, segment.seq_num)
                if segment.seq_num == expected:
                    if not segment.fin:
                        rcvd_data.extend(segment.payload)
                    ack.ack_num = expected
                    expected = (expected + 1) % RDTSegment.SEQ_NUM_BOUND
                super().sendto(ack.encode(), remote_address)
                if segment.fin:
                    break
            except TimeoutException:
                if timeout_count < 0:
                    continue
                timeout_count += 1
                logging.info('timed out, count=%d', timeout_count)
                if timeout_count > socket.MAX_RETRY_TIMES:
                    raise ConnectionAbortedError('timed out')
            except ValueError:
                super().sendto(ack.encode(), remote_address)

        # self.setblocking(True)
        logging.info('----------- receipt finished -----------')
        return bytes(rcvd_data), remote_address


    def sendto(self, data_to_send: bytes, address: tuple):
        total_len = len(data_to_send)
        UNIT = RDTSegment.MAX_PAYLOAD_LEN

        base = 0  # to be acked
        next = 0
        win = deque(maxlen=socket.WIN_SIZE)
        logging.info('ready to send...')

        # Send data
        timeout_count = 0
        while base * UNIT < total_len:
            # enqueue
            while next < base + socket.WIN_SIZE:
                # logging.debug('next=%d', next)
                if next * UNIT > total_len:
                    break
                # FIXME: meaningless ack_num (since full duplex transmission is not supported yet)
                pkt = RDTSegment(data_to_send[next*UNIT:next*UNIT+UNIT], seq_num=next, ack_num=0)
                win.append(pkt)
                next += 1

            # send all segments in the window
            for pkt in win:
                super().sendto(pkt.encode(), address)
                logging.debug('sent #%d', pkt.seq_num)

            # handle acknowledgements
            # self.settimeout(socket.TIMEOUT)
            while True:
                try:
                    # assumption: no truncated packets
                    # data, remote_address = super().recvfrom(RDTSegment.SEGMENT_LEN)
                    data, remote_address = self._timeout_recvfrom(RDTSegment.SEGMENT_LEN)
                    assert remote_address == address
                    rcvd_ack = RDTSegment.parse(data)
                    timeout_count = 0  # no error, reset counter

                    assert rcvd_ack.ack
                    logging.info('#%d acked', rcvd_ack.ack_num)
                    # cumulative ack
                    assert ((win[0].seq_num <= rcvd_ack.ack_num <= win[-1].seq_num) or
                            (win[0].seq_num > win[-1].seq_num and (rcvd_ack.ack_num <= win[-1].seq_num or
                                                                   rcvd_ack.ack_num >= win[0].seq_num)))
                    while True:
                        front = win.popleft().seq_num
                        base += 1
                        logging.debug('base=%d', base)
                        if front == rcvd_ack.ack_num:
                            break
                    logging.debug('win.length = %d', len(win))

                    # all acked
                    if len(win) == 0:  # or, if base == next
                        break
                except ValueError:
                    logging.info('corrupted ack, ignored')
                except AssertionError:
                    logging.info('duplicate ack or unexpected segment received')
                except TimeoutException:
                    timeout_count += 1
                    logging.info('timed out, count=%d', timeout_count)
                    if timeout_count > socket.MAX_RETRY_TIMES:
                        raise ConnectionError('timed out')
                    break

        # Finish
        fin_seq = next % RDTSegment.SEQ_NUM_BOUND
        fin_pkt = RDTSegment(None, seq_num=fin_seq, ack_num=0, fin=True).encode()  # FIXME: meaningless ack_num
        fin_err_count = 0
        while True:
            try:
                super().sendto(fin_pkt, address)
                # data, remote_address = super().recvfrom(RDTSegment.SEGMENT_LEN)
                data, remote_address = self._timeout_recvfrom(RDTSegment.SEGMENT_LEN)

                # limited by the required APIs to provide, the receipt of the last FINACK
                # is not guaranteed, though a high probability is provided
                rcvd_ack = RDTSegment.parse(data)
                if rcvd_ack.ack and rcvd_ack.ack_num == fin_seq:
                    break
            except (TimeoutException, ValueError):
                fin_err_count += 1
                if fin_err_count > socket.MAX_RETRY_TIMES:
                    break
        # self.setblocking(True)
        logging.info('----------- all sent -----------')

    def _timeout_recvfrom(self, buffer_size, timeout=TIMEOUT):
        # This implementation uses SIGALRM signal to set timeout for recvfrom(),
        # and consequently it is incompatible with Windows.
        #
        # Note that socket.settimeout() can provide better compatibility
        # if we do not need to care about time.sleep()
        signal.setitimer(signal.ITIMER_REAL, timeout)
        ans = super().recvfrom(buffer_size)
        signal.setitimer(signal.ITIMER_REAL, 0)
        return ans

    def close(self):
        # not necessary for connectionless RDT
        raise NotImplementedError

    def accept(self):
        raise NotImplementedError

    def connect(self, address):
        raise NotImplementedError

    def recv(self, buffer_size: int):
        raise NotImplementedError

    def send(self, data: bytes):
        raise NotImplementedError


class RDTSegment:
    """
    Reliable Data Transfer Segment

    Segment Format:

      0   1   2   3   4   5   6   7   8   9   a   b   c   d   e   f
    +---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
    |VERSION|SYN|FIN|ACK|                  LENGTH                   |
    +---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
    |             SEQ #             |             ACK #             |
    +---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
    |                           CHECKSUM                            |
    +---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
    |                                                               |
    /                            PAYLOAD                            /
    /                                                               /
    +---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+

    Protocol Version:           1

    Flags:
     - SYN                      Synchronize
     - FIN                      Finish
     - ACK                      Acknowledge

    Ranges:
     - Payload Length           0 - 1440  (append zeros to the end if length < 1440)
     - Sequence Number          0 - 63
     - Acknowledgement Number   0 - 63

    Checksum Algorithm:         16 bit one's complement of the one's complement sum

    Size of sender's window     16
    """

    HEADER_LEN = 6
    MAX_PAYLOAD_LEN = 1440
    SEGMENT_LEN = MAX_PAYLOAD_LEN + HEADER_LEN
    SEQ_NUM_BOUND = 64

    def __init__(self, payload: bytes, seq_num: int, ack_num: int, syn: bool=False, fin: bool=False, ack: bool=False):
        self.syn = syn
        self.fin = fin
        self.ack = ack
        self.seq_num = seq_num % RDTSegment.SEQ_NUM_BOUND
        self.ack_num = ack_num % RDTSegment.SEQ_NUM_BOUND
        if payload is not None and len(payload) > RDTSegment.MAX_PAYLOAD_LEN:
            raise ValueError
        self.payload = payload

    def encode(self) -> bytes:
        """Returns fixed length bytes"""
        head = 0x4000 | (len(self.payload) if self.payload else 0)  # protocol version: 1
        if self.syn:
            head |= 0x2000
        if self.fin:
            head |= 0x1000
        if self.ack:
            head |= 0x0800
        arr = bytearray(struct.pack('!HBBH', head, self.seq_num, self.ack_num, 0))
        if self.payload:
            arr.extend(self.payload)
        checksum = RDTSegment.calc_checksum(arr)
        arr[4] = checksum >> 8
        arr[5] = checksum & 0xFF
        arr.extend(b'\x00' * (RDTSegment.SEGMENT_LEN - len(arr)))  # so that the total length is fixed
        return bytes(arr)

    @staticmethod
    def parse(segment: Union[bytes, bytearray]) -> 'RDTSegment':
        """Parse raw bytes into an RDTSegment object"""
        try:
            assert len(segment) == RDTSegment.SEGMENT_LEN
            # assert 0 <= len(segment) - 6 <= RDTSegment.MAX_PAYLOAD_LEN
            assert RDTSegment.calc_checksum(segment) == 0
            head, = struct.unpack('!H', segment[0:2])
            version = (head & 0xC000) >> 14
            assert version == 1
            syn = (head & 0x2000) != 0
            fin = (head & 0x1000) != 0
            ack = (head & 0x0800) != 0
            length = head & 0x07FF
            # assert length + 6 == len(segment)
            seq_num, ack_num, checksum = struct.unpack('!BBH', segment[2:6])
            payload = segment[6:6+length]
            return RDTSegment(payload, seq_num, ack_num, syn, fin, ack)
        except AssertionError as e:
            raise ValueError from e

    @staticmethod
    def calc_checksum(segment: Union[bytes, bytearray]) -> int:
        """
        :param segment: raw bytes of a segment, with its checksum set to 0
        :return: 16-bit unsigned checksum
        """
        i = iter(segment)
        bytes_sum = sum(((a << 8) + b for a, b in zip(i, i)))  # for a, b: (s[0], s[1]), (s[2], s[3]), ...
        if len(segment) % 2 == 1:  # pad zeros to form a 16-bit word for checksum
            bytes_sum += segment[-1] << 8
        # add the overflow at the end (adding twice is sufficient)
        bytes_sum = (bytes_sum & 0xFFFF) + (bytes_sum >> 16)
        bytes_sum = (bytes_sum & 0xFFFF) + (bytes_sum >> 16)
        return ~bytes_sum & 0xFFFF
