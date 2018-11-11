#!/usr/bin/env python3

import logging
from rdt import socket
from time import time


SERVER_ADDR = '127.0.0.1'
SERVER_PORT = 9999

with open('alice.txt', 'rb') as f:
    DATA = f.read()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='[CLIENT %(levelname)s] %(asctime)s: %(message)s')
    client = socket()
    start_time = time()
    client.sendto(DATA, (SERVER_ADDR, SERVER_PORT))
    data, server_addr = client.recvfrom()
    rtt = time() - start_time
    assert data == DATA
    print('Received: ', data)
    print('Round trip time:', rtt)
