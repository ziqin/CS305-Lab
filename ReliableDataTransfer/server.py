#!/usr/bin/env python3

import logging
from rdt import socket


SERVER_ADDR = '127.0.0.1'
SERVER_PORT = 9999


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='[SERVER %(levelname)s] %(asctime)s: %(message)s')
    server = socket()
    server.bind((SERVER_ADDR, SERVER_PORT))
    while True:
        try:
            data, client_addr = server.recvfrom()
            server.sendto(data, client_addr)
        except ConnectionError:
            logging.exception('Connection aborted by the client')
        except KeyboardInterrupt:
            logging.info('Quit.')
            break
