#!/usr/bin/env python3

"""Web File Browser"""

__author__ = 'Jeeken (Wang Ziqin)'
__email__ = '11712310@mail.sustc.edu.cn'
__version__ = '2.1'


import handler
import logging
import os.path
import sys

import web


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s: %(message)s')

    if sys.version_info < (3, 4):
        print('Python 3.4+ is required', file=sys.stderr)
        sys.exit(-1)
    elif sys.version_info < (3, 7):
        print('Python 3.7+ is expected')

    try:
        if len(sys.argv) == 2:
            port = 8080
        elif len(sys.argv) == 3:
            port = int(sys.argv[2])
        else:
            raise ValueError
        assert os.path.isdir(sys.argv[1])
    except (ValueError, AssertionError):
        print('Usage:\n\tpython main.py <root-directory> [port]')
        sys.exit(0)

    try:
        server = web.HttpServer(host='localhost', port=port, root_dir=sys.argv[1].rstrip('/'))
        server.add_handlers(
            handler.FileRangeTransHandler,
            handler.LastVisitHandler,
            handler.DirBrowseHandler,
            handler.FileTransHandler
        )
        server.run()
    except PermissionError:
        print('You may need root privilege', file=sys.stderr)
    except OSError as e:
        print(e.args[1], file=sys.stderr)
