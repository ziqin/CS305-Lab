#!/usr/bin/env python

# TODO: refactor, eliminating duplicates

import logging
import socket as sock
import time

from dns_msg import Message
from socketserver import UDPServer, DatagramRequestHandler


def send_and_recv_datagram(server_address: tuple, data, buf_size: int = 4096) -> bytes:
    """Sends a UDP packet to a host and retrieve response from it"""
    client_sock = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
    client_sock.sendto(data, server_address)
    response, server_address = client_sock.recvfrom((buf_size))
    client_sock.close()
    return response


class DNSResolver(UDPServer):
    class QueryHandler(DatagramRequestHandler):
        def handle(self):
            query_data = self.rfile.read(self.server.buf_size)
            query = Message.parse(query_data)
            logging.info('Got query')

            if query.header['op_code'] != 0:
                return

            now = time.time()
            try:
                # check existence and TTL of cache
                valid = all((self.server.cache[q.cache_key].expiration >= now for q in query.questions))
            except KeyError:
                valid = False

            if valid:  # use cached records
                resp = Message()
                resp.header['id'] = query.header['id']
                resp.header['rd'] = query.header['rd']
                resp.header['ra'] = False  # recursive query not supported currently
                resp.questions = query.questions
                resp.answers = [self.server.cache[q.cache_key] for q in query.questions]
                logging.info('cached records used')
            else:  # forward to upstream
                logging.info('forwarding to upstream')
                upstream_resp = send_and_recv_datagram(self.server.upstream_address, query_data, self.server.buf_size)
                resp = Message.parse(upstream_resp)
                logging.info('got response from upstream')
                for rr in resp.answers:
                    self.server.cache[rr.cache_key] = rr
                    logging.info('cache: record %s added or updated', rr.cache_key)
                for rr in resp.authority:
                    self.server.cache[rr.cache_key] = rr
                    logging.info('cache: record %s added or updated', rr.cache_key)
                for rr in resp.additional:
                    # EDNS ignored
                    if rr.r_type in (Message.QType.A, Message.QType.AAAA, Message.QType.CNAME,
                                     Message.QType.TXT, Message.QType.NS, Message.QType.MX):
                        self.server.cache[rr.cache_key] = rr
                        logging.info('cache: record %s added or updated', rr.cache_key)

            self.wfile.write(resp.encode())
            logging.info('%d answers replied to client', resp.header['an_count'])

    def __init__(self, upstream_host, upstream_port=53, hostname='localhost', serving_port=53, buf_size=4096):
        super().__init__((hostname, serving_port), DNSResolver.QueryHandler)
        self.upstream_address = upstream_host, upstream_port
        self.buf_size = buf_size
        self.cache = {}


def main():
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(asctime)s: %(message)s')

    logging.info('Local DNS resolver working')
    server = DNSResolver(upstream_host='ns2.sustc.edu.cn', upstream_port=53, hostname='localhost', serving_port=53)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info('Quit')
    except Exception:
        logging.exception('Oops!')


if __name__ == '__main__':
    main()
