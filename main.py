#!/usr/bin/env python3

"""Web File Browser"""

__author__ = 'Jeeken (Wang Ziqin)'
__email__ = '11712310@mail.sustc.edu.cn'
__version__ = '1.2'


import sys
import logging

import web

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(asctime)s: %(message)s')
    if sys.version_info < (3, 4):
        logging.critical('Python 3.4+ is required')
        sys.exit(-1)
    elif sys.version_info < (3, 7):
        logging.warning('Python 3.7+ is expected')
    server = web.HttpServer(host='127.0.0.1', port=8080)
    server.run()
