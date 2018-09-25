#!/usr/bin/env python3

"""Echo with asyncio"""

__author__ = 'Jeeken (Wang Ziqin)'
__version__ = '1.0'

import asyncio

HOST = '127.0.0.1'
PORT = 5555

async def connected_callback(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    while True:
        client_address = writer.get_extra_info('peername')
        data = await reader.readline()
        if data and data != b'exit\r\n':
            writer.write(data)
            print('{} sent: {}'.format(client_address, data))
        else:
            writer.close()
            break


def echo():
    loop = asyncio.get_event_loop()
    coroutine = asyncio.start_server(connected_callback, HOST, PORT, loop=loop)
    server = loop.run_until_complete(coroutine)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()


if __name__ == '__main__':
    echo()
