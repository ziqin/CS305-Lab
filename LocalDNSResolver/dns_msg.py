# TODO: refactor

import math
import struct
import time

from collections import namedtuple
from enum import Enum


class Message:
    class MsgType(Enum):
        Question = 0
        Response = 1

    class QType(Enum):
        A = 1
        NS = 2
        MD = 3
        MF = 4
        CNAME = 5
        SOA = 6
        MB = 7
        MG = 8
        MR = 9
        NULL = 10
        WKS = 11
        PTR = 12
        HINFO = 13
        MINFO = 14
        MX = 15
        TXT = 16
        AAAA = 28
        AXFR = 252
        MAILB = 253
        MAILA = 254
        ALL = 255

    class QClass(Enum):
        IN = 1
        CS = 2
        CH = 3
        HS = 4


    class Question(namedtuple('Question', ['name', 'q_type', 'q_class'])):
        @property
        def cache_key(self):
            return '{}#{}#{}'.format('.'.join(self.name), self.q_type, self.q_class)

    class ResRecord(namedtuple('ResRecord', ['name', 'r_type', 'r_class', 'expiration', 'r_length', 'r_data'])):
        @property
        def cache_key(self):
            return '{}#{}#{}'.format('.'.join(self.name), self.r_type, self.r_class)

    def __init__(self):
        self.header = dict(
            id=0,
            qr=Message.MsgType.Question,
            op_code=0,
            aa=False,
            tc=False,
            rd=False,
            ra=False,
            z=0,
            r_code=0,
            qd_count=0,
            an_count=0,
            ns_count=0,
            ar_count=0
        )
        self.questions = []
        self.answers = []
        self.authority = []
        self.additional = []

    @staticmethod
    def parse(data: bytes):
        """
        Parse DNS message defined in RFC 1035 4.1

        +---------------------+
        |        Header       |
        +---------------------+
        |       Question      | the question for the name server
        +---------------------+
        |        Answer       | RRs answering the question
        +---------------------+
        |      Authority      | RRs pointing toward an authority
        +---------------------+
        |      Additional     | RRs holding additional information
        +---------------------+
        """
        try:
            msg = Message()
            offset = 12  # length of header == 12
            msg.header = Message.parse_header(data[0:offset])
            for i in range(msg.header['qd_count']):
                question, offset = Message.parse_question(data, offset)
                msg.questions.append(question)
            for i in range(msg.header['an_count']):
                rr, offset = Message.parse_rr(data, offset)
                msg.answers.append(rr)
            for i in range(msg.header['ns_count']):
                rr, offset = Message.parse_rr(data, offset)
                msg.authority.append(rr)
            for i in range(msg.header['ar_count']):
                rr, offset = Message.parse_rr(data, offset)
                msg.additional.append(rr)
            return msg
        except IndexError as e:
            raise ValueError from e

    def encode(self) -> bytes:
        """Pack a DNS message into bytes that can be transferred"""
        self.header['qd_count'] = len(self.questions)
        self.header['an_count'] = len(self.answers)
        self.header['ns_count'] = len(self.authority)
        self.header['ar_count'] = len(self.additional)
        encoded = [Message.dump_header(self.header)]
        encoded.extend((Message.dump_question(q) for q in self.questions))
        encoded.extend((Message.dump_rr(ans) for ans in self.answers))
        encoded.extend((Message.dump_rr(auth) for auth in self.authority))
        encoded.extend((Message.dump_rr(addi) for addi in self.additional))
        return b''.join(encoded)

    @staticmethod
    def parse_header(header_data: bytes):
        """
        Parse header section based on RFC 1035 4.1.1

                                        1  1  1  1  1  1
          0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                      ID                       |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE   |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    QDCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    ANCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    NSCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    ARCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        """
        try:
            fields = struct.unpack('!6H', header_data)
        except struct.error as e:
            raise ValueError from e

        flags = fields[1]
        return dict(id=fields[0],
                      qr=Message.MsgType.Question if (flags & 0x8000) == 0 else Message.MsgType.Response,
                      op_code=(flags & 0x7800) >> 11,
                      aa=(flags & 0x0400) != 0,
                      tc=(flags & 0x0200) != 0,
                      rd=(flags & 0x0100) != 0,
                      ra=(flags & 0x0080) != 0,
                      z=(flags & 0x0070) >> 4,
                      r_code=(flags & 0x000f),
                      qd_count=fields[2],
                      an_count=fields[3],
                      ns_count=fields[4],
                      ar_count=fields[5])

    @staticmethod
    def dump_header(header):
        """Pack a DNS message into bytes that can be transferred"""
        flags = 0
        if header['qr'] is Message.MsgType.Response:
            flags |= 0x8000
        flags |= (header['op_code'] & 0xf) << 11
        if header['aa']:
            flags |= 0x0400
        if header['tc']:
            flags |= 0x0200
        if header['rd']:
            flags |= 0x0100
        if header['ra']:
            flags |= 0x0800
        flags |= (header['z'] & 0x7) << 4
        flags |= header['r_code'] & 0xf
        return struct.pack('!6H', header['id'], flags,
                           header['qd_count'], header['an_count'], header['ns_count'], header['ar_count'])

    @staticmethod
    def parse_name(data: bytes, offset: int) -> tuple:
        """
        Parse domain name, truncating domain name into labels

        :return: a list of domain name labels, and the offset after processing name
        """

        idx = offset
        name = []
        rightmost = offset  # index of the rightmost byte processed
        while data[idx] != 0 and idx - offset < 256:  # length of a name field won't exceed 255
            is_pointer = data[idx] & 0xc0 == 0xc0  # domain name compression (RFC 1035 4.1.4)
            if is_pointer:
                rightmost = max(rightmost, idx + 1)
                pointer, = struct.unpack('!H', data[idx:idx+2])
                idx = pointer & 0x3fff  # the offset part
            else:
                next_idx = idx + data[idx] + 1
                try:
                    name.append(data[idx+1:next_idx].decode())
                except (UnicodeDecodeError, IndexError) as e:
                    raise ValueError from e
                idx = next_idx
                rightmost = max(rightmost, idx)
        return name, rightmost + 1

    @staticmethod
    def dump_name(nodes: list) -> bytes:
        """Convert a list of name nodes into bytes using RFC 1035 QNAME representation"""
        name = []
        for node in nodes:
            node_encoded = node.encode()
            name.append(struct.pack('!B', len(node_encoded)))
            name.append(node_encoded)
        name.append(struct.pack('B', 0))
        return b''.join(name)

    @staticmethod
    def parse_question(data: bytes, offset: int) -> tuple:
        """
        Parse header section defined in RFC 1035 4.1.2

                                        1  1  1  1  1  1
          0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                                               |
        /                     QNAME                     /
        /                                               /
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                     QTYPE                     |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                     QCLASS                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

        :return: a Message.Question instance, and the offset after processing the question
        """
        name, offset = Message.parse_name(data, offset)
        q_type, q_class = struct.unpack('!2H', data[offset:offset+4])
        return Message.Question(name, q_type, q_class), offset+4

    @staticmethod
    def dump_question(question) -> bytes:
        """Convert a Message.Question instance into bytes"""
        return b''.join([Message.dump_name(question.name), struct.pack('!2H', question.q_type, question.q_class)])

    @staticmethod
    def parse_rr(data: bytes, offset: int) -> tuple:
        """
        Parse a DNS resource record defined in RFC 1035 4.1.3

                                        1  1  1  1  1  1
          0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                                               |
        /                                               /
        /                      NAME                     /
        |                                               |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                      TYPE                     |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                     CLASS                     |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                      TTL                      |
        |                                               |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                   RDLENGTH                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--|
        /                     RDATA                     /
        /                                               /
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

        :return: a Message.Record instance, and the offset after processing the record
        """
        name, new_offset = Message.parse_name(data, offset)
        rr_type, rr_class, ttl, length = struct.unpack('!2H1I1H', data[new_offset:new_offset+10])
        res_data = data[new_offset+10:new_offset+10+length]
        return Message.ResRecord(name, rr_type, rr_class, ttl+time.time(), length, res_data), new_offset+10+length

    @staticmethod
    def dump_rr(rr) -> bytes:
        """Convert a DNS resource record into bytes"""
        ttl = math.floor(rr.expiration - time.time())
        return b''.join([Message.dump_name(rr.name),
                         struct.pack('!2H1I1H', rr.r_type, rr.r_class, ttl if ttl >= 0 else 0, rr.r_length),
                         rr.r_data])
